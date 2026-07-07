"""Corpus view: após o sorteio, o analista vê só os artigos sorteados."""

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
def analista(db):
    return User.objects.create_user(username="a", email="a@u.edu", password="x", pode_anco=True)


@pytest.fixture
def projeto(db, analista):
    p = ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    return p


def _item(projeto, titulo, ident):
    art = Artigo.objects.create(titulo=titulo, ano=2023)
    return ItemCorpus.objects.create(
        projeto=projeto, titulo=titulo, identificador=ident, artigo=art
    )


def _corpus(client, projeto, **params):
    url = reverse("anco_corpus", args=[projeto.slug])
    return client.get(url, params)


def test_sem_sorteio_mostra_todos(client, projeto, analista):
    a = _item(projeto, "Art A", "k1")
    b = _item(projeto, "Art B", "k2")
    client.force_login(analista)
    resp = _corpus(client, projeto)
    assert resp.status_code == 200
    assert a.titulo.encode() in resp.content
    assert b.titulo.encode() in resp.content


def test_apos_sorteio_mostra_so_atribuidos(client, projeto, analista):
    a = _item(projeto, "Atribuido pra mim", "k1")
    b = _item(projeto, "Nao atribuido", "k2")
    sorteio = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=sorteio, analista=analista, artigo=a.artigo)

    client.force_login(analista)
    resp = _corpus(client, projeto)  # sem filtro → default "meus"
    assert a.titulo.encode() in resp.content
    assert b.titulo.encode() not in resp.content


def test_filtro_todos_ignora_sorteio(client, projeto, analista):
    a = _item(projeto, "Atribuido AAA", "k1")
    b = _item(projeto, "Outro BBB", "k2")
    sorteio = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=sorteio, analista=analista, artigo=a.artigo)

    client.force_login(analista)
    resp = _corpus(client, projeto, filtro="todos")
    assert a.titulo.encode() in resp.content
    assert b.titulo.encode() in resp.content


def test_analista_sem_atribuicao_apos_sorteio_ve_corpus(client, projeto, analista):
    # Há sorteio, mas este analista não recebeu nada → default cai em "todos".
    a = _item(projeto, "Livre CCC", "k1")
    outro = User.objects.create_user(username="o", email="o@u.edu", password="x", pode_anco=True)
    MembroANCO.objects.create(projeto=projeto, usuario=outro, papel=MembroANCO.Papel.ANALISTA)
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=outro, artigo=a.artigo)

    client.force_login(analista)
    resp = _corpus(client, projeto)
    assert a.titulo.encode() in resp.content  # vê o corpus, não filtra vazio
