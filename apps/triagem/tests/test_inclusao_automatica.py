"""Modo ANCO sem triagem: importar já inclui tudo no corpus + promove."""

import pytest

from apps.acervo.models import Artigo
from apps.triagem.importacao import importar_para_busca
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem

pytestmark = pytest.mark.django_db

_St = RegistroTriagem.Status

RIS = """TY  - JOUR
TI  - Cognitive analysis in science education
AU  - Silva, J.
PY  - 2020
DO  - 10.1000/anco1
AB  - A study about cognition.
ER  -

TY  - THES
TI  - Uma tese sobre análise cognitiva
AU  - Souza, M.
PY  - 2021
DO  - 10.1000/anco2
ER  -
"""


def _registros():
    from apps.triagem.importacao import parse_ris

    return parse_ris(RIS)


@pytest.fixture
def proj_anco(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


@pytest.fixture
def proj_rigoroso(db):
    return ProtocoloTriagem.objects.create(nome="Rigoroso")  # default RIGOROSO


def test_import_anco_inclui_e_promove(proj_anco):
    b = Busca.objects.create(protocolo=proj_anco)
    importar_para_busca(b, _registros())
    regs = proj_anco.registros.all()
    assert regs.count() == 2  # artigo + tese (todos os tipos entram)
    assert all(r.status == _St.INCLUIDO for r in regs)
    assert all(r.artigo_id is not None for r in regs)
    assert Artigo.objects.filter(eh_legado=False).count() == 2


def test_import_rigoroso_nao_inclui(proj_rigoroso):
    b = Busca.objects.create(protocolo=proj_rigoroso)
    importar_para_busca(b, _registros())
    regs = proj_rigoroso.registros.all()
    assert regs.count() == 2
    assert all(r.status == _St.IDENTIFICADO for r in regs)  # aguarda triagem
    assert all(r.artigo_id is None for r in regs)


def test_reimport_anco_idempotente(proj_anco):
    b = Busca.objects.create(protocolo=proj_anco)
    importar_para_busca(b, _registros())
    importar_para_busca(b, _registros())  # de novo
    assert proj_anco.registros.count() == 2  # não duplicou
    assert Artigo.objects.filter(eh_legado=False).count() == 2


def test_ja_no_acervo_nao_e_incluido(proj_anco):
    # Artigo legado pré-existente casa pelo DOI → fica isento (ja_no_acervo).
    Artigo.objects.create(doi="10.1000/anco1", titulo="Legado", eh_legado=True)
    b = Busca.objects.create(protocolo=proj_anco)
    importar_para_busca(b, _registros())
    casado = proj_anco.registros.get(doi="10.1000/anco1")
    assert casado.ja_no_acervo is True
    assert casado.status == _St.IDENTIFICADO  # não promovido — acervo intocado
    assert casado.artigo.eh_legado is True
