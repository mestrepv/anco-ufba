"""Painel: analista ANCO é levado à worklist de sorteados (não à lista global)."""

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
    return User.objects.create_user(
        username="ana", email="ana@u.edu", password="x",
        papel=User.Papel.ANALISTA, pode_anco=True,
    )


@pytest.fixture
def projeto(db, analista):
    p = ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    return p


def _sorteia(projeto, analista, titulo, ident):
    art = Artigo.objects.create(titulo=titulo, ano=2023)
    ItemCorpus.objects.create(projeto=projeto, titulo=titulo, identificador=ident, artigo=art)
    s = SorteioANCO.objects.filter(projeto=projeto).first() or SorteioANCO.objects.create(
        projeto=projeto
    )
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=art)
    return art


def test_proximo_passo_leva_a_worklist_anco(client, projeto, analista):
    _sorteia(projeto, analista, "Sorteado 1", "k1")
    _sorteia(projeto, analista, "Sorteado 2", "k2")
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    prox = resp.context["proxima"]
    assert prox is not None
    # Aponta para a worklist ANCO, não para a lista global de análises.
    assert prox["href"] == reverse("anco_analisar", args=[projeto.slug])
    assert reverse("minhas_analises") != prox["href"]
    assert "sorteado" in prox["titulo"].lower()


def test_conta_so_pendentes(client, projeto, analista):
    a = _sorteia(projeto, analista, "Feito", "k1")
    _sorteia(projeto, analista, "A fazer", "k2")
    # Uma já submetida → não conta como pendente.
    Analise.objects.create(artigo=a, analista=analista, status=Analise.Status.SUBMETIDA)
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert "1 artigo" in resp.context["proxima"]["titulo"]


def test_card_anco_tem_cta_analisar(client, projeto, analista):
    _sorteia(projeto, analista, "Sorteado", "k1")
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    card = next(c for c in resp.context["projetos_anco"] if c["projeto"].pk == projeto.pk)
    assert card["n_atribuidos"] == 1
    assert card["n_pendentes"] == 1
    assert reverse("anco_analisar", args=[projeto.slug]).encode() in resp.content


def test_sem_sorteio_nao_forca_worklist(client, projeto, analista):
    # Sem sorteio: não há próximo passo ANCO (cai no comportamento anterior).
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    prox = resp.context["proxima"]
    if prox:  # se houver, não deve ser a worklist ANCO (não há sorteados)
        assert prox["href"] != reverse("anco_analisar", args=[projeto.slug])
