"""Fase 11.1 — concordância entre revisores (Fleiss κ + % acordo)."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem import concordancia as conc
from apps.triagem.models import DecisaoTriagem, ProtocoloTriagem, RegistroTriagem

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db
DEC = RegistroTriagem.Decisao


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def revs(db):
    return [
        User.objects.create_user(
            username=f"rv{i}",
            email=f"rv{i}@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        for i in range(2)
    ]


def _decidido(protocolo, revs, decisoes, doi):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="T", doi=doi)
    agora = timezone.now()
    for rev, dec in zip(revs, decisoes, strict=True):
        DecisaoTriagem.objects.create(
            registro=reg, revisor=rev, decisao=dec, prazo_em=agora, concluido_em=agora
        )
    return reg


def test_sem_itens_decididos(protocolo):
    r = conc.calcular(protocolo)
    assert r.n_itens == 0
    assert r.kappa is None


def test_kappa_e_acordo(protocolo, revs):
    # 3 concordam, 1 diverge → acordo 0.75; κ de Fleiss ≈ 0.47 (moderada)
    _decidido(protocolo, revs, [DEC.INCLUIR, DEC.INCLUIR], "10.1/a")
    _decidido(protocolo, revs, [DEC.EXCLUIR, DEC.EXCLUIR], "10.1/b")
    _decidido(protocolo, revs, [DEC.INCLUIR, DEC.INCLUIR], "10.1/c")
    _decidido(protocolo, revs, [DEC.INCLUIR, DEC.EXCLUIR], "10.1/d")
    r = conc.calcular(protocolo)
    assert r.n_itens == 4
    assert r.n_revisores == 2
    assert r.perc_acordo == pytest.approx(0.75)
    assert r.perc_pct == 75
    assert r.kappa == pytest.approx(0.4667, abs=0.005)
    assert r.interpretacao == "moderada"


def test_ignora_itens_incompletos(protocolo, revs):
    # registro com só 1 decisão concluída → não entra no cálculo
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="X", doi="10.2/x")
    DecisaoTriagem.objects.create(
        registro=reg,
        revisor=revs[0],
        decisao=DEC.INCLUIR,
        prazo_em=timezone.now(),
        concluido_em=timezone.now(),
    )
    DecisaoTriagem.objects.create(
        registro=reg, revisor=revs[1], prazo_em=timezone.now()
    )  # pendente
    assert conc.calcular(protocolo).n_itens == 0


@pytest.fixture
def analista(db):
    return membro(
        User.objects.create_user(
            username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )


def test_prisma_exibe_e_exporta_concordancia(client, protocolo, revs, analista):
    _decidido(protocolo, revs, [DEC.INCLUIR, DEC.INCLUIR], "10.3/a")
    _decidido(protocolo, revs, [DEC.INCLUIR, DEC.EXCLUIR], "10.3/b")
    client.force_login(analista)
    html = client.get(turl("triagem_prisma"))
    assert "Concordância entre revisores".encode() in html.content
    assert b"Fleiss" in html.content
    js = client.get(turl("triagem_prisma"), {"formato": "json"})
    dados = js.json()
    assert dados["concordancia_n_itens"] == 2
    assert "concordancia_fleiss_kappa" in dados
