"""Acompanhamento da equipe — dados por membro e gate de curador."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.anco.estatisticas import acompanhamento_membros
from apps.anco.models import (
    AtribuicaoANCO,
    FonteImport,
    ItemCorpus,
    MembroANCO,
    ProjetoANCO,
    SorteioANCO,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(username="cur", email="cur@u.edu", password="x", pode_anco=True)


@pytest.fixture
def analista(db):
    return User.objects.create_user(username="ana", email="ana@u.edu", password="x", pode_anco=True)


@pytest.fixture
def inativo(db):
    return User.objects.create_user(username="ina", email="ina@u.edu", password="x", pode_anco=True)


@pytest.fixture
def projeto(db, curador, analista, inativo):
    p = ProjetoANCO.objects.create(nome="Piloto ANCO", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=curador, papel=MembroANCO.Papel.CURADOR)
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    MembroANCO.objects.create(projeto=p, usuario=inativo, papel=MembroANCO.Papel.ANALISTA)
    return p


def _linha(linhas, user):
    return next(ln for ln in linhas if ln["usuario"] == user)


def test_fontes_e_itens_por_membro(projeto, analista):
    fonte = FonteImport.objects.create(projeto=projeto, criado_por=analista, outra_base="WoS")
    item = ItemCorpus.objects.create(projeto=projeto, titulo="T1", identificador="k1")
    item.origem_fontes.add(fonte)
    # Item removido não conta.
    removido = ItemCorpus.objects.create(
        projeto=projeto, titulo="T2", identificador="k2", removido=True
    )
    removido.origem_fontes.add(fonte)

    ln = _linha(acompanhamento_membros(projeto), analista)
    assert ln["n_fontes"] == 1
    assert ln["n_itens"] == 1
    assert ln["tem_atividade"] is True
    assert ln["ultima_atividade"] is not None


def test_analises_no_projeto_vs_espontaneas(projeto, analista):
    atribuido = Artigo.objects.create(titulo="Atribuído", ano=2021)
    avulso = Artigo.objects.create(titulo="Avulso", ano=2022)
    legado = Artigo.objects.create(titulo="Legado", ano=2019)
    sorteio = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=sorteio, analista=analista, artigo=atribuido)

    Analise.objects.create(artigo=atribuido, analista=analista, status=Analise.Status.SUBMETIDA)
    Analise.objects.create(artigo=avulso, analista=analista, status=Analise.Status.RASCUNHO)
    # Legado nunca conta como trabalho do piloto.
    Analise.objects.create(artigo=legado, analista=analista, status=Analise.Status.LEGADO)

    ln = _linha(acompanhamento_membros(projeto), analista)
    assert ln["n_atribuidos"] == 1
    assert ln["no_projeto"] == {"rascunho": 0, "submetida": 1, "publicada": 0, "total": 1}
    assert ln["espontaneas"] == {"rascunho": 1, "submetida": 0, "publicada": 0, "total": 1}


def test_membro_sem_atividade(projeto, inativo):
    ln = _linha(acompanhamento_membros(projeto), inativo)
    assert ln["tem_atividade"] is False
    assert ln["ultima_atividade"] is None
    assert ln["n_fontes"] == ln["n_itens"] == ln["n_atribuidos"] == 0


def test_view_curador_200(client, projeto, curador, inativo):
    client.force_login(curador)
    resp = client.get(reverse("anco_acompanhamento", args=[projeto.slug]))
    assert resp.status_code == 200
    assert b"Acompanhamento da equipe" in resp.content
    assert inativo.email.encode() in resp.content


def test_view_analista_403(client, projeto, analista):
    client.force_login(analista)
    resp = client.get(reverse("anco_acompanhamento", args=[projeto.slug]))
    assert resp.status_code == 403
