"""Fase 11.5 — calibração (piloto): amostra comum, κ de Fleiss, gate de prontidão."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem import calibracao as cal
from apps.triagem.models import (
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
    RodadaCalibracao,
)

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db

Dec = RegistroTriagem.Decisao
Et = DecisaoTriagem.Etapa


def _revisor(n, **kw):
    return membro(User.objects.create_user(
        username=f"rev{n}", email=f"rev{n}@u.edu", password="x",
        papel=User.Papel.ANALISTA, revisor_aprovado=True, aceita_revisoes=True, **kw
    ))


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def equipe(db):
    return [_revisor(i) for i in range(3)]


@pytest.fixture
def registros(db, protocolo):
    return [
        RegistroTriagem.objects.create(protocolo=protocolo, titulo=f"T{i}", doi=f"10.1/{i}")
        for i in range(6)
    ]


def test_iniciar_designa_toda_equipe(protocolo, equipe, registros):
    rodada = cal.iniciar_calibracao(protocolo, tamanho=4, criada_por=equipe[0])
    assert rodada is not None
    assert rodada.registros.count() == 4
    assert rodada.n_revisores == 3
    # 4 itens × 3 revisores = 12 decisões de calibração.
    assert DecisaoTriagem.objects.filter(etapa=Et.CALIBRACAO).count() == 12


def test_calibracao_nao_muda_status_do_registro(protocolo, equipe, registros):
    cal.iniciar_calibracao(protocolo, tamanho=2)
    for r in registros:
        r.refresh_from_db()
        assert r.status == RegistroTriagem.Status.IDENTIFICADO


def test_sem_equipe_suficiente_nao_inicia(protocolo, registros):
    _revisor(99)  # só um revisor aprovado
    assert cal.iniciar_calibracao(protocolo, tamanho=3) is None


def _triar_todos(rodada, decisao_por_revisor):
    """Conclui as decisões de calibração; decisao_por_revisor: {revisor_id: decisao}."""
    for d in DecisaoTriagem.objects.filter(
        registro__in=rodada.registros.all(), etapa=Et.CALIBRACAO
    ):
        d.decisao = decisao_por_revisor[d.revisor_id]
        d.concluido_em = timezone.now()
        d.save()


def test_acordo_total_kappa_perfeito(protocolo, equipe, registros):
    rodada = cal.iniciar_calibracao(protocolo, tamanho=3)
    _triar_todos(rodada, {r.id: Dec.INCLUIR for r in equipe})
    res = cal.calcular(rodada)
    assert res.completos == 3
    assert res.perc_acordo == 1.0
    # Sem variância entre categorias, κ é indefinido (None) — mas acordo total.
    assert res.kappa is None or res.kappa == pytest.approx(1.0)


def test_calcular_pronto_quando_kappa_alto(protocolo, equipe, registros):
    rodada = cal.iniciar_calibracao(protocolo, tamanho=4)
    itens = list(rodada.registros.all())
    # 3 itens consenso incluir, 1 item consenso excluir → κ perfeito por categoria.
    mapa = {
        itens[0].id: [Dec.INCLUIR] * 3,
        itens[1].id: [Dec.INCLUIR] * 3,
        itens[2].id: [Dec.EXCLUIR] * 3,
        itens[3].id: [Dec.EXCLUIR, Dec.INCLUIR, Dec.INCLUIR],  # divergência
    }
    for r in itens:
        for i, d in enumerate(
            DecisaoTriagem.objects.filter(registro=r, etapa=Et.CALIBRACAO).order_by("revisor_id")
        ):
            d.decisao = mapa[r.id][i]
            d.concluido_em = timezone.now()
            d.save()
    res = cal.calcular(rodada)
    assert res.completos == 4
    assert res.kappa is not None


def test_fechar_congela_resultado(protocolo, equipe, registros):
    rodada = cal.iniciar_calibracao(protocolo, tamanho=3)
    _triar_todos(rodada, {r.id: (Dec.INCLUIR if i else Dec.EXCLUIR) for i, r in enumerate(equipe)})
    res = cal.fechar_calibracao(rodada)
    rodada.refresh_from_db()
    assert rodada.fechada_em is not None
    assert rodada.kappa == res.kappa


# ── view ───────────────────────────────────────────────────────────────────


def test_view_curador_inicia(client, protocolo, registros):
    curador = membro(User.objects.create_user(
        username="cur", email="cur@u.edu", password="x",
        papel=User.Papel.CURADOR, revisor_aprovado=True, aceita_revisoes=True,
    ), papel="curador")
    _revisor(1)
    _revisor(2)
    client.force_login(curador)
    r = client.post(turl("triagem_calibracao"), {"acao": "iniciar", "tamanho": "3"})
    assert r.status_code == 302
    assert RodadaCalibracao.objects.count() == 1


def test_view_analista_nao_inicia(client, protocolo, equipe):
    client.force_login(equipe[0])
    r = client.post(turl("triagem_calibracao"), {"acao": "iniciar", "tamanho": "3"})
    assert r.status_code == 403


def test_view_get_renderiza(client, equipe):
    client.force_login(equipe[0])
    r = client.get(turl("triagem_calibracao"))
    assert r.status_code == 200
    assert "Calibra" in r.content.decode("utf-8")
