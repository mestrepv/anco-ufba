"""Testes das views da Fase 3 (criacao/edicao de analises)."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.acervo.services import LinkCheckResultado
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()


@pytest.fixture
def vocab(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana",
        email="ana@usp.edu.br",
        password="x",
        papel=User.Papel.ANALISTA,
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit",
        email="l@usp.edu.br",
        password="x",
        papel=User.Papel.LEITOR,
    )


@pytest.fixture
def artigo(db, vocab):
    return Artigo.objects.create(
        doi="10.1234/teste",
        titulo="Artigo de teste",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://example.org/teste",
    )


@pytest.fixture
def cliente_analista(client, analista):
    client.force_login(analista)
    return client


# ----------------------------------------------------------------------
# Acesso controlado
# ----------------------------------------------------------------------


class TestAcessoControlado:
    def test_anonimo_redireciona_login(self, db, client):
        for url_name in ("minhas_analises", "cadastrar_artigo"):
            resp = client.get(reverse(url_name))
            assert resp.status_code in (301, 302)
            assert "/accounts/login/" in resp["Location"]

    def test_leitor_recebe_403(self, db, client, leitor):
        client.force_login(leitor)
        resp = client.get(reverse("cadastrar_artigo"))
        assert resp.status_code == 403

    def test_buscar_redireciona_para_cadastrar(self, cliente_analista):
        resp = cliente_analista.get(reverse("buscar_artigo"))
        assert resp.status_code in (301, 302)
        assert reverse("cadastrar_artigo") in resp["Location"]


# ----------------------------------------------------------------------
# Cadastro de artigo
# ----------------------------------------------------------------------


class TestCadastrarArtigo:
    def test_get_renderiza_form(self, cliente_analista):
        resp = cliente_analista.get(reverse("cadastrar_artigo"))
        assert resp.status_code == 200
        # Header editorial M6: "Nova análise"
        assert "Nova análise".encode() in resp.content

    @patch("apps.acervo.views.validar_link")
    def test_post_valido_cria_artigo_e_analise(
        self, mock_validar, cliente_analista, vocab, analista
    ):
        mock_validar.return_value = LinkCheckResultado(status="ok", codigo_http=200, url_final=None)
        resp = cliente_analista.post(
            reverse("cadastrar_artigo"),
            data={
                "doi": "10.99/novo",
                "titulo": "Artigo novo",
                "titulo_periodico": "Periodico Y",
                "ano": "2021",
                "volume": "",
                "numero": "",
                "pagina_inicial": "",
                "pagina_final": "",
                "area": "Ciências Humanas",
                "autores": "Autor X",
                "vinculacao_institucional": "",
                "palavras_chaves": "",
                "resumo": "",
                "base_consulta": vocab.pk,
                "link_acesso": "https://example.org/novo",
                "link_acesso_alternativo": "",
                "artigo_pago": "",
                "acesso_aberto": "",
            },
        )
        assert resp.status_code == 302
        artigo = Artigo.objects.get(doi="10.99/novo")
        assert artigo.eh_legado is False
        analise = Analise.objects.get(artigo=artigo, analista=analista)
        assert analise.status == Analise.Status.RASCUNHO
        # mock foi chamado
        mock_validar.assert_called_once()


class TestIniciarAnalise:
    def test_post_cria_ou_recupera(self, cliente_analista, artigo, analista):
        url = reverse("iniciar_analise", args=[artigo.pk])
        # Primeira vez: cria
        resp = cliente_analista.post(url)
        assert resp.status_code == 302
        assert Analise.objects.filter(artigo=artigo, analista=analista).count() == 1
        # Segunda vez: nao duplica
        cliente_analista.post(url)
        assert Analise.objects.filter(artigo=artigo, analista=analista).count() == 1


# ----------------------------------------------------------------------
# Edicao multipasso
# ----------------------------------------------------------------------


@pytest.fixture
def analise_rascunho(db, analista, artigo):
    return Analise.objects.create(artigo=artigo, analista=analista)


class TestEditarAnalise:
    def test_get_passo_identificacao(self, cliente_analista, analise_rascunho):
        url = reverse("editar_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.get(url)
        assert resp.status_code == 200
        assert b"Identifica" in resp.content

    def test_get_passo_presenca_renderiza_form(self, cliente_analista, analise_rascunho):
        url = reverse("editar_analise", args=[analise_rascunho.pk]) + "?passo=presenca"
        resp = cliente_analista.get(url)
        assert resp.status_code == 200
        assert b"presenca_titulo" in resp.content

    def test_post_passo_estrutura_salva_e_avanca(self, cliente_analista, analise_rascunho):
        url = reverse("editar_analise", args=[analise_rascunho.pk]) + "?passo=estrutura"
        resp = cliente_analista.post(
            url,
            data={
                "objeto": "obj",
                "objetivo": "obj2",
                "foco": "foco",
                "metodologia": "met",
                "referenciais": "refs",
                "resultados": "res",
                "contexto_producao": "",
                "observacoes": "",
            },
        )
        assert resp.status_code == 302
        analise_rascunho.refresh_from_db()
        assert analise_rascunho.objeto == "obj"

    def test_outro_analista_nao_pode_editar(self, db, client, analise_rascunho):
        outro = User.objects.create_user(
            username="outro",
            email="o@usp.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        client.force_login(outro)
        url = reverse("editar_analise", args=[analise_rascunho.pk])
        resp = client.get(url)
        assert resp.status_code == 403

    def test_analise_submetida_redireciona(self, cliente_analista, analise_rascunho):
        analise_rascunho.status = Analise.Status.SUBMETIDA
        analise_rascunho.save()
        url = reverse("editar_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.get(url)
        assert resp.status_code == 302


# ----------------------------------------------------------------------
# Auto-save
# ----------------------------------------------------------------------


class TestAutoSave:
    def test_post_salva_e_responde_json(self, cliente_analista, analise_rascunho):
        url = reverse("autosave_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.post(
            url,
            data={
                "objeto": "salvo via autosave",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        analise_rascunho.refresh_from_db()
        assert analise_rascunho.objeto == "salvo via autosave"

    def test_outro_usuario_recebe_403(self, db, client, analise_rascunho):
        outro = User.objects.create_user(
            username="o2",
            email="o2@usp.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        client.force_login(outro)
        url = reverse("autosave_analise", args=[analise_rascunho.pk])
        resp = client.post(url, data={"objeto": "x"})
        assert resp.status_code == 403

    def test_analise_nao_rascunho_recusa(self, cliente_analista, analise_rascunho):
        analise_rascunho.status = Analise.Status.SUBMETIDA
        analise_rascunho.save()
        url = reverse("autosave_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.post(url, data={"objeto": "x"})
        assert resp.status_code == 400
        assert resp.json()["ok"] is False


# ----------------------------------------------------------------------
# Submeter
# ----------------------------------------------------------------------


class TestSubmeter:
    def test_get_renderiza_confirmacao(self, cliente_analista, analise_rascunho):
        url = reverse("submeter_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.get(url)
        assert resp.status_code == 200
        assert b"Submeter" in resp.content

    def test_post_muda_status_e_seta_submetida_em(self, cliente_analista, analise_rascunho):
        url = reverse("submeter_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.post(url)
        assert resp.status_code == 302
        analise_rascunho.refresh_from_db()
        assert analise_rascunho.status == Analise.Status.SUBMETIDA
        assert analise_rascunho.submetida_em is not None

    def test_submeter_avisa_que_aguarda_curadoria(self, cliente_analista, analise_rascunho):
        url = reverse("submeter_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.post(url, follow=True)
        assert resp.status_code == 200
        msgs = list(resp.context["messages"])
        assert any("curadoria" in str(m).lower() for m in msgs)

    def test_analise_ja_submetida_redireciona_sem_alterar(self, cliente_analista, analise_rascunho):
        analise_rascunho.status = Analise.Status.SUBMETIDA
        analise_rascunho.save()
        url = reverse("submeter_analise", args=[analise_rascunho.pk])
        resp = cliente_analista.post(url)
        assert resp.status_code == 302


# ----------------------------------------------------------------------
# Minhas analises
# ----------------------------------------------------------------------


class TestMinhasAnalises:
    def test_lista_apenas_proprias(self, cliente_analista, analise_rascunho, db, vocab):
        outro = User.objects.create_user(
            username="o3",
            email="o3@usp.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        outro_artigo = Artigo.objects.create(
            doi="10.0/outro",
            titulo="outra",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://example.org/outro",
        )
        Analise.objects.create(artigo=outro_artigo, analista=outro)
        resp = cliente_analista.get(reverse("minhas_analises"))
        assert resp.status_code == 200
        analises = resp.context["analises"]
        assert all(
            a.analista_id == cliente_analista.session.get("_auth_user_id", None)
            or a.analista_id == int(cliente_analista.session["_auth_user_id"])
            for a in analises
        )
        assert analise_rascunho in list(analises)
