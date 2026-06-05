"""Fase 13 — relevância por correspondência de termos (sem embeddings)."""

import pytest

from apps.triagem.models import ProtocoloTriagem, RegistroTriagem
from apps.triagem.relevancia import (
    recalcular_protocolo,
    score_registro,
    termos_do_protocolo,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    p = ProtocoloTriagem.ativo()
    p.termos_realce = "cognitive analysis, knowledge, Fróes"
    p.save()
    return p


def _reg(protocolo, **kw):
    base = dict(titulo="T", status=RegistroTriagem.Status.INCLUIDO)
    base.update(kw)
    return RegistroTriagem.objects.create(protocolo=protocolo, **base)


def test_termos_do_protocolo_normaliza_e_remove_curtos(protocolo):
    termos = termos_do_protocolo(protocolo)
    assert "cognitive analysis" in termos
    assert "knowledge" in termos
    assert "froes" in termos  # sem acento, caixa-baixa


def test_score_conta_termos_distintos_sem_acento(protocolo):
    reg = _reg(
        protocolo,
        titulo="Cognitive Analysis of knowledge",
        resumo="A study by FROES on cognition.",
        palavras_chaves="",
    )
    # casa: "cognitive analysis", "knowledge", "froes" = 3
    assert score_registro(reg) == 3


def test_score_zero_sem_correspondencia(protocolo):
    reg = _reg(protocolo, titulo="Unrelated paper", resumo="nothing here")
    assert score_registro(reg) == 0


def test_sem_termos_score_zero():
    p = ProtocoloTriagem.objects.create(nome="vazio", termos_realce="")
    reg = _reg(p, titulo="Anything")
    assert termos_do_protocolo(p) == [] or score_registro(reg) == 0


def test_recalcular_protocolo_persiste(protocolo):
    reg = _reg(protocolo, titulo="cognitive analysis & knowledge", relevancia_score=0)
    n = recalcular_protocolo(protocolo)
    reg.refresh_from_db()
    assert n >= 1
    assert reg.relevancia_score == 2
