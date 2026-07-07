"""Tela 'Analisar artigos' (worklist do analista): mostra SÓ os sorteados, sem filtro."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
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


def _analisar(client, projeto):
    return client.get(reverse("anco_analisar", args=[projeto.slug]))


def test_mostra_so_sorteados_para_mim(client, projeto, analista):
    meu = _item(projeto, "Meu artigo sorteado", "k1")
    _item(projeto, "Artigo de outro", "k2")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=meu.artigo)

    client.force_login(analista)
    resp = _analisar(client, projeto)
    assert resp.status_code == 200
    assert b"Meu artigo sorteado" in resp.content
    assert b"Artigo de outro" not in resp.content


def test_sem_filtros_troca_conjunto(client, projeto, analista):
    """A tela não expõe os filtros do corpus (meus/todos/acervo/novos)."""
    meu = _item(projeto, "Sorteado", "k1")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=meu.artigo)

    client.force_login(analista)
    resp = _analisar(client, projeto)
    corpo = resp.content
    # Nenhum link de filtro para "todos"/"acervo" que ampliaria o conjunto.
    assert b"filtro=todos" not in corpo
    assert b"filtro=acervo" not in corpo


def test_sem_sorteio_estado_claro(client, projeto, analista):
    _item(projeto, "No corpus", "k1")  # existe corpus, mas sem sorteio
    client.force_login(analista)
    resp = _analisar(client, projeto)
    assert resp.status_code == 200
    assert "sorteio ainda não foi feito".encode() in resp.content


def test_sorteado_sem_nada_para_mim(client, projeto, analista):
    a = _item(projeto, "Do outro", "k1")
    outro = User.objects.create_user(username="o", email="o@u.edu", password="x", pode_anco=True)
    MembroANCO.objects.create(projeto=projeto, usuario=outro, papel=MembroANCO.Papel.ANALISTA)
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=outro, artigo=a.artigo)

    client.force_login(analista)
    resp = _analisar(client, projeto)
    assert "Nenhum artigo foi sorteado para você".encode() in resp.content


def test_progresso_conta_concluidas(client, projeto, analista):
    a = _item(projeto, "Feito", "k1")
    b = _item(projeto, "A fazer", "k2")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=a.artigo)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=b.artigo)
    # Uma análise submetida (conta como concluída), a outra nem começou.
    Analise.objects.create(
        artigo=a.artigo, analista=analista, status=Analise.Status.SUBMETIDA
    )

    client.force_login(analista)
    resp = _analisar(client, projeto)
    ctx = resp.context
    assert ctx["total"] == 2
    assert ctx["concluidas"] == 1
    assert ctx["n_falta"] == 1
    assert ctx["pct"] == 50


def test_a_fazer_vem_antes(client, projeto, analista):
    feito = _item(projeto, "ZZZ concluido", "k1")
    falta = _item(projeto, "AAA a fazer", "k2")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=feito.artigo)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=falta.artigo)
    Analise.objects.create(
        artigo=feito.artigo, analista=analista, status=Analise.Status.PUBLICADA
    )

    client.force_login(analista)
    resp = _analisar(client, projeto)
    corpo = resp.content.decode()
    # O "a fazer" aparece antes do "concluído" na página.
    assert corpo.index("AAA a fazer") < corpo.index("ZZZ concluido")
