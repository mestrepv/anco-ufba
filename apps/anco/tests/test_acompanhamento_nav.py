"""Navegação pelos artigos sorteados de um analista (a partir do acompanhamento)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.anco.models import (
    AtribuicaoANCO,
    ItemCorpus,
    MembroANCO,
    ProjetoANCO,
    SorteioANCO,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", pode_anco=True, papel="curador"
    )


@pytest.fixture
def analista(db):
    return User.objects.create_user(username="ana", email="ana@u.edu", password="x", pode_anco=True)


@pytest.fixture
def projeto(db, curador, analista):
    p = ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=curador, papel=MembroANCO.Papel.CURADOR)
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    return p


def _item(projeto, titulo, ident):
    art = Artigo.objects.create(titulo=titulo, ano=2023)
    return ItemCorpus.objects.create(
        projeto=projeto, titulo=titulo, identificador=ident, artigo=art
    )


def test_nav_abre_primeiro_sorteado_com_ctx(client, projeto, curador, analista):
    a = _item(projeto, "Sorteado 1", "k1")
    b = _item(projeto, "Sorteado 2", "k2")
    _item(projeto, "Nao sorteado", "k3")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=a.artigo)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=b.artigo)

    client.force_login(curador)
    resp = client.get(reverse("anco_acompanhamento_nav", args=[projeto.slug, analista.id]))
    # Redireciona para a ficha do 1º sorteado, com o contexto do analista.
    assert resp.status_code == 302
    assert reverse("anco_corpus_editar", args=[projeto.slug, a.pk]) in resp.url
    assert f"ctx=analista&analista={analista.id}" in resp.url


def test_navegacao_restrita_aos_sorteados(client, projeto, curador, analista):
    a = _item(projeto, "Sorteado A", "k1")
    b = _item(projeto, "Sorteado B", "k2")
    _item(projeto, "Fora do sorteio", "k3")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=a.artigo)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=b.artigo)

    client.force_login(curador)
    url = reverse("anco_corpus_editar", args=[projeto.slug, a.pk])
    resp = client.get(url, {"ctx": "analista", "analista": analista.id})
    assert resp.status_code == 200
    assert resp.context["total"] == 2  # só os 2 sorteados, não o corpus inteiro
    assert resp.context["rotulo_nav"] == "Artigo sorteado"
    # próximo aponta para o outro sorteado, preservando o contexto
    assert str(b.pk) in resp.context["url_proximo"]
    assert "ctx=analista" in resp.context["url_proximo"]


def test_sem_sorteados_volta_ao_acompanhamento(client, projeto, curador, analista):
    client.force_login(curador)
    resp = client.get(reverse("anco_acompanhamento_nav", args=[projeto.slug, analista.id]))
    assert resp.status_code == 302
    assert reverse("anco_acompanhamento", args=[projeto.slug]) in resp.url


def test_analista_comum_nao_acessa(client, projeto, analista):
    client.force_login(analista)
    resp = client.get(reverse("anco_acompanhamento_nav", args=[projeto.slug, analista.id]))
    assert resp.status_code == 403
