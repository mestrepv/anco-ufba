"""Visualização (curador) da análise de um analista — modo leitura, mesma tela."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", papel=User.Papel.CURADOR
    )


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="ana@u.edu", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def artigo(db):
    return Artigo.objects.create(titulo="Obra sorteada", ano=2023)


def _url(artigo, analista):
    return reverse("ver_analise_analista", args=[artigo.pk, analista.pk])


def test_analise_existente_renderiza_em_leitura(client, curador, analista, artigo):
    Analise.objects.create(
        artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO, objeto="meu objeto"
    )
    client.force_login(curador)
    resp = client.get(_url(artigo, analista))
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "Modo leitura" in corpo
    assert "disabled" in corpo  # fieldset desabilitado
    assert resp.context["somente_leitura"] is True
    assert resp.context["analise"].objeto == "meu objeto"


def test_sem_analise_monta_transitoria_e_link_funciona(client, curador, analista, artigo):
    # Analista ainda NÃO iniciou — o link deve funcionar mesmo assim.
    assert not Analise.objects.filter(artigo=artigo, analista=analista).exists()
    client.force_login(curador)
    resp = client.get(_url(artigo, analista))
    assert resp.status_code == 200
    assert resp.context["analise_transitoria"] is True
    assert "ainda não foi iniciada" in resp.content.decode()
    # E nada foi gravado: continua sem análise no banco.
    assert not Analise.objects.filter(artigo=artigo, analista=analista).exists()


def test_analista_comum_nao_acessa(client, analista, artigo):
    outro = User.objects.create_user(
        username="o", email="o@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    client.force_login(outro)
    resp = client.get(_url(artigo, analista))
    assert resp.status_code == 403


def test_leitura_nao_tem_botao_submeter(client, curador, analista, artigo):
    Analise.objects.create(artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO)
    client.force_login(curador)
    resp = client.get(_url(artigo, analista))
    assert b"Submeter para curadoria" not in resp.content
    assert b"Salvar agora" not in resp.content


def test_enviada_mostra_aprovar_e_devolver(client, curador, analista, artigo):
    Analise.objects.create(artigo=artigo, analista=analista, status=Analise.Status.SUBMETIDA)
    client.force_login(curador)
    resp = client.get(_url(artigo, analista))
    corpo = resp.content.decode()
    assert resp.context["pode_aprovar"] is True
    assert "Aprovar e publicar" in corpo
    assert "Devolver" in corpo


def test_rascunho_nao_mostra_decisao(client, curador, analista, artigo):
    Analise.objects.create(artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO)
    client.force_login(curador)
    resp = client.get(_url(artigo, analista))
    assert resp.context["pode_aprovar"] is False
    assert "Aprovar e publicar" not in resp.content.decode()


def test_aprovar_da_visualizacao_com_next(client, curador, analista, artigo):
    analise = Analise.objects.create(
        artigo=artigo, analista=analista, status=Analise.Status.SUBMETIDA
    )
    client.force_login(curador)
    destino = "/anco/p/piloto-x/sorteio/"
    resp = client.post(reverse("aprovar_analise", args=[analise.pk]), {"next": destino})
    assert resp.status_code == 302
    assert resp["Location"] == destino
    analise.refresh_from_db()
    assert analise.status == Analise.Status.PUBLICADA
