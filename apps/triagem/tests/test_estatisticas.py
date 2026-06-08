"""Estatística artigos × bases (corpus pós-dedup)."""

import pytest

from apps.triagem.estatisticas import estatisticas_por_base
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo

pytestmark = pytest.mark.django_db

_St = RegistroTriagem.Status


@pytest.fixture
def proj(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


def _incluido(proj, doi, *buscas):
    reg = RegistroTriagem.objects.create(
        protocolo=proj, titulo=f"R {doi}", doi=doi, status=_St.INCLUIDO
    )
    for b in buscas:
        reg.origem_buscas.add(b)
    promover_para_acervo(reg)
    return reg


def test_exclusivos_compartilhados_e_dedup(proj):
    scopus = Busca.objects.create(protocolo=proj, outra_base="Scopus")
    wos = Busca.objects.create(protocolo=proj, outra_base="WoS")
    _incluido(proj, "10/só-scopus", scopus)  # exclusivo Scopus
    _incluido(proj, "10/só-wos", wos)  # exclusivo WoS
    _incluido(proj, "10/ambas", scopus, wos)  # compartilhado

    est = estatisticas_por_base(proj)
    assert est.total_unicos == 3
    assert est.total_aparicoes == 4  # 1 + 1 + 2
    assert est.duplicados_removidos == 1  # 4 − 3
    por = {linha.base: linha for linha in est.por_base}
    assert por["Scopus"].total == 2 and por["Scopus"].exclusivos == 1
    assert por["Scopus"].compartilhados == 1
    assert por["WoS"].total == 2 and por["WoS"].compartilhados == 1


def test_corpus_vazio(proj):
    est = estatisticas_por_base(proj)
    assert est.total_unicos == 0
    assert est.por_base == []
    assert est.duplicados_removidos == 0
