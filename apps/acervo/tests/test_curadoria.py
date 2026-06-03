"""Testes da fila de curadoria: aprovação de análises e confirmação de resenhas."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo, Resenha
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
        username="autor", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur", email="c@u.edu.br", password="x", papel=User.Papel.CURADOR
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit", email="l@u.edu.br", password="x", papel=User.Papel.LEITOR
    )


@pytest.fixture
def artigo(db, vocab):
    return Artigo.objects.create(
        doi="10.x/t", titulo="T", ano=2020, base_consulta=vocab,
        link_acesso="https://e.org/t",
    )


@pytest.fixture
def analise_submetida(db, artigo, autor):
    return Analise.objects.create(
        artigo=artigo, analista=autor, status=Analise.Status.SUBMETIDA
    )


@pytest.fixture
def resenha_revisada(db, analise_submetida):
    return Resenha.objects.create(
        analise=analise_submetida, texto="R", status=Resenha.Status.REVISADA
    )


class TestAcesso:
    def test_leitor_recebe_403(self, client, leitor):
        client.force_login(leitor)
        assert client.get(reverse("fila_curadoria")).status_code == 403

    def test_curador_ve_fila(self, client, curador, analise_submetida, resenha_revisada):
        client.force_login(curador)
        resp = client.get(reverse("fila_curadoria"))
        assert resp.status_code == 200
        assert analise_submetida in list(resp.context["analises"])
        assert resenha_revisada in list(resp.context["resenhas"])


class TestAprovacaoAnalise:
    def test_aprovar_publica(self, client, curador, analise_submetida):
        client.force_login(curador)
        resp = client.post(reverse("aprovar_analise", args=[analise_submetida.pk]))
        assert resp.status_code == 302
        analise_submetida.refresh_from_db()
        assert analise_submetida.status == Analise.Status.PUBLICADA
        assert analise_submetida.aprovada_por_id == curador.pk
        assert analise_submetida.publicada_em is not None

    def test_devolver_ajustes_volta_rascunho(self, client, curador, analise_submetida):
        client.force_login(curador)
        resp = client.post(
            reverse("devolver_analise", args=[analise_submetida.pk]),
            data={"acao": "ajustes", "motivo": "Faltou metodologia."},
        )
        assert resp.status_code == 302
        analise_submetida.refresh_from_db()
        assert analise_submetida.status == Analise.Status.RASCUNHO
        assert analise_submetida.motivo_curadoria == "Faltou metodologia."

    def test_rejeitar(self, client, curador, analise_submetida):
        client.force_login(curador)
        client.post(
            reverse("devolver_analise", args=[analise_submetida.pk]),
            data={"acao": "rejeitar", "motivo": "Fora de escopo."},
        )
        analise_submetida.refresh_from_db()
        assert analise_submetida.status == Analise.Status.REJEITADA

    def test_leitor_nao_aprova(self, client, leitor, analise_submetida):
        client.force_login(leitor)
        resp = client.post(reverse("aprovar_analise", args=[analise_submetida.pk]))
        assert resp.status_code == 403
        analise_submetida.refresh_from_db()
        assert analise_submetida.status == Analise.Status.SUBMETIDA


class TestConfirmacaoResenha:
    def test_confirmar_publica(self, client, curador, resenha_revisada):
        client.force_login(curador)
        resp = client.post(reverse("confirmar_resenha", args=[resenha_revisada.pk]))
        assert resp.status_code == 302
        resenha_revisada.refresh_from_db()
        assert resenha_revisada.status == Resenha.Status.PUBLICADA
        assert resenha_revisada.confirmada_por_id == curador.pk
        assert resenha_revisada.publicada_em is not None

    def test_rejeitar_resenha(self, client, curador, resenha_revisada):
        client.force_login(curador)
        client.post(reverse("rejeitar_resenha", args=[resenha_revisada.pk]))
        resenha_revisada.refresh_from_db()
        assert resenha_revisada.status == Resenha.Status.REJEITADA
