"""Migração para o corpus: incluir_corpus_total inclui pendentes e reinclui
os excluídos da autotriagem antiga (tratada como obsoleta)."""

import pytest

from apps.triagem.aprovacao import incluir_corpus_total
from apps.triagem.models import ProtocoloTriagem, RegistroTriagem

pytestmark = pytest.mark.django_db

_St = RegistroTriagem.Status


@pytest.fixture
def proj_anco(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


def _reg(proj, doi, status, ja_no_acervo=False):
    return RegistroTriagem.objects.create(
        protocolo=proj, titulo=f"R {doi}", doi=doi, status=status, ja_no_acervo=ja_no_acervo
    )


def test_inclui_identificados_e_reinclui_excluidos(proj_anco):
    ident = _reg(proj_anco, "10/i", _St.IDENTIFICADO)
    exc = _reg(proj_anco, "10/e", _St.EXCLUIDO)
    isento = _reg(proj_anco, "10/leg", _St.IDENTIFICADO, ja_no_acervo=True)

    n = incluir_corpus_total(proj_anco)
    assert n == 2  # identificado + excluído reincluído
    ident.refresh_from_db()
    exc.refresh_from_db()
    isento.refresh_from_db()
    assert ident.status == _St.INCLUIDO and ident.artigo_id is not None
    assert exc.status == _St.INCLUIDO and exc.artigo_id is not None  # exclusão desfeita
    assert isento.status == _St.IDENTIFICADO and isento.artigo_id is None  # intocado


def test_idempotente(proj_anco):
    _reg(proj_anco, "10/a", _St.IDENTIFICADO)
    assert incluir_corpus_total(proj_anco) == 1
    assert incluir_corpus_total(proj_anco) == 0  # nada pendente na 2ª passagem
    assert proj_anco.registros.filter(status=_St.INCLUIDO).count() == 1


def test_rejeita_projeto_rigoroso(db):
    rig = ProtocoloTriagem.objects.create(nome="Rig")  # default RIGOROSO
    _reg(rig, "10/x", _St.IDENTIFICADO)
    assert incluir_corpus_total(rig) == 0
    assert rig.registros.get(doi="10/x").status == _St.IDENTIFICADO
