"""Testes da Fase 6: task de links, actions de admin, dashboard."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from apps.acervo.admin import LinkQuebrado, LinkQuebradoAdmin
from apps.acervo.models import Analise, Artigo, SnapshotLink
from apps.acervo.services import LinkCheckResultado
from apps.acervo.tasks import task_verificar_links
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def vocab(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def autor(db):
    return User.objects.create_user(
        username="autor",
        email="a@u.edu.br",
        password="x",
        papel=User.Papel.ANALISTA,
    )


@pytest.fixture
def artigo_publicado(db, vocab, autor):
    a = Artigo.objects.create(
        doi="10.1/teste",
        titulo="X",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://example.org/x",
    )
    Analise.objects.create(artigo=a, analista=autor, status=Analise.Status.PUBLICADA)
    return a


@pytest.fixture
def artigo_rascunho(db, vocab, autor):
    """Artigo cuja unica analise eh rascunho — nao deve ser verificado."""
    a = Artigo.objects.create(
        doi="10.2/rascunho",
        titulo="Y",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://example.org/y",
    )
    Analise.objects.create(artigo=a, analista=autor, status=Analise.Status.RASCUNHO)
    return a


# ----------------------------------------------------------------------
# task_verificar_links
# ----------------------------------------------------------------------


class TestTaskVerificarLinks:
    @patch("apps.acervo.tasks.validar_link")
    def test_processa_apenas_artigos_com_analise_publicada(
        self, mock_validar, artigo_publicado, artigo_rascunho
    ):
        mock_validar.return_value = LinkCheckResultado(
            status="ok",
            codigo_http=200,
            url_final=None,
        )
        resultado = task_verificar_links()
        assert resultado["total"] == 1
        # validar_link chamado apenas para o publicado
        urls = [c.args[0] for c in mock_validar.call_args_list]
        assert artigo_publicado.link_acesso in urls
        assert artigo_rascunho.link_acesso not in urls

    @patch("apps.acervo.tasks.validar_link")
    def test_persiste_resultado_no_artigo(self, mock_validar, artigo_publicado):
        mock_validar.return_value = LinkCheckResultado(
            status="quebrado",
            codigo_http=404,
            url_final=None,
            mensagem="HTTP 404",
        )
        task_verificar_links()
        artigo_publicado.refresh_from_db()
        assert artigo_publicado.link_status == "quebrado"
        assert artigo_publicado.link_ultima_verificacao is not None

    @patch("apps.acervo.tasks.validar_link")
    def test_excecao_eh_capturada_e_contada(self, mock_validar, artigo_publicado):
        mock_validar.side_effect = RuntimeError("boom")
        resultado = task_verificar_links()
        # nao quebra, conta como pulado
        assert resultado["pulados"] == 1


# ----------------------------------------------------------------------
# LinkQuebrado proxy admin
# ----------------------------------------------------------------------


class TestLinkQuebradoProxy:
    def test_changelist_filtra_apenas_quebrados(self, db, vocab, autor):
        # Cria artigos com status diferentes de link
        ok = Artigo.objects.create(
            doi="10.ok/x",
            titulo="ok",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/ok",
            link_status=Artigo.LinkStatus.OK,
        )
        quebrado = Artigo.objects.create(
            doi="10.q/x",
            titulo="quebrado",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/q",
            link_status=Artigo.LinkStatus.QUEBRADO,
        )

        from django.contrib.admin.sites import AdminSite

        admin_instance = LinkQuebradoAdmin(LinkQuebrado, AdminSite())
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(
            username="adm",
            email="a@a.com",
            password="x",
        )
        qs = admin_instance.get_queryset(request)
        ids = list(qs.values_list("id", flat=True))
        assert quebrado.pk in ids
        assert ok.pk not in ids


class TestActionsArtigoAdmin:
    @patch("apps.acervo.admin.validar_link")
    def test_action_verificar_link_atualiza(
        self, mock_validar, db, vocab, autor, artigo_publicado, admin_client
    ):
        mock_validar.return_value = LinkCheckResultado(
            status="ok",
            codigo_http=200,
            url_final=None,
        )
        url = reverse("admin:acervo_artigo_changelist")
        resp = admin_client.post(
            url,
            {
                "action": "verificar_link_selecionados",
                "_selected_action": [str(artigo_publicado.pk)],
            },
            follow=True,
        )
        assert resp.status_code == 200
        artigo_publicado.refresh_from_db()
        assert artigo_publicado.link_status == "ok"

    def test_action_marcar_indisponivel(self, db, autor, artigo_publicado, admin_client):
        url = reverse("admin:acervo_artigo_changelist")
        resp = admin_client.post(
            url,
            {
                "action": "marcar_como_indisponivel",
                "_selected_action": [str(artigo_publicado.pk)],
            },
            follow=True,
        )
        assert resp.status_code == 200
        artigo_publicado.refresh_from_db()
        assert artigo_publicado.link_status == Artigo.LinkStatus.QUEBRADO

    @patch("apps.acervo.admin.capturar_snapshot_wayback")
    def test_action_promover_snapshot_existente(
        self, mock_captura, db, autor, artigo_publicado, admin_client
    ):
        # Cria snapshot pre-existente
        SnapshotLink.objects.create(
            artigo=artigo_publicado,
            url_original=artigo_publicado.link_acesso,
            url_wayback="https://web.archive.org/web/20260101/x",
        )
        url = reverse("admin:acervo_artigo_changelist")
        admin_client.post(
            url,
            {
                "action": "promover_snapshot_wayback",
                "_selected_action": [str(artigo_publicado.pk)],
            },
            follow=True,
        )
        artigo_publicado.refresh_from_db()
        assert "web.archive.org" in artigo_publicado.link_acesso
        # mock NAO chamado porque ja havia snapshot
        mock_captura.assert_not_called()


# ----------------------------------------------------------------------
# Dashboard widgets
# ----------------------------------------------------------------------


class TestDashboard:
    def test_admin_home_renderiza_widgets(self, db, autor, artigo_publicado, admin_client):
        # Garante metricas != 0
        Artigo.objects.filter(pk=artigo_publicado.pk).update(
            link_status=Artigo.LinkStatus.QUEBRADO,
        )
        resp = admin_client.get("/admin/")
        assert resp.status_code == 200
        assert b"Painel de curadoria" in resp.content
        assert b"Links quebrados" in resp.content

    def test_calcular_metricas_consistente(self, db, autor, artigo_publicado):
        from apps.core.admin_dashboard import calcular_metricas

        Artigo.objects.filter(pk=artigo_publicado.pk).update(
            link_status=Artigo.LinkStatus.QUEBRADO,
        )
        m = calcular_metricas()
        assert m["links_quebrados"] >= 1
        assert "publicada" in m["analises_por_status"]


# ----------------------------------------------------------------------
# Setup de schedules
# ----------------------------------------------------------------------


class TestSetupSchedules:
    def test_command_idempotente(self, db):
        from django.core.management import call_command
        from django_q.models import Schedule

        call_command("setup_q_schedules")
        n1 = Schedule.objects.count()
        call_command("setup_q_schedules")
        n2 = Schedule.objects.count()
        assert n1 == n2  # idempotente
        # schedules esperados
        nomes = set(Schedule.objects.values_list("name", flat=True))
        assert "verificar_prazos_revisao" in nomes
        assert "verificar_saude_dos_links" in nomes
