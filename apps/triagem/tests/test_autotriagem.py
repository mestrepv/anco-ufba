"""Fase 13 — autotriagem (Revisão ANCO): o dono tria a própria base."""

import pytest
from django.contrib.auth import get_user_model

from apps.triagem.autotriagem import (
    autotriar,
    pode_autotriar,
    registros_para_autotriar,
)
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def proj_anco(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.termos_realce = "cognitive analysis"
    p.save()
    return p


@pytest.fixture
def importador(db):
    return membro(
        User.objects.create_user(
            username="imp",
            email="imp@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
        )
    )


@pytest.fixture
def outro(db):
    return membro(
        User.objects.create_user(
            username="out",
            email="out@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
        )
    )


def _reg_da_base(protocolo, dono, doi="10/x", titulo="Cognitive analysis paper"):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo=titulo,
        doi=doi,
        ano=2022,
        status=RegistroTriagem.Status.IDENTIFICADO,
    )
    busca = Busca.objects.create(protocolo=protocolo, criado_por=dono)
    reg.origem_buscas.add(busca)
    return reg


def test_so_modo_anco_permite_autotriar(importador):
    rig = ProtocoloTriagem.objects.create(nome="rigoroso")  # default RIGOROSO
    reg = _reg_da_base(rig, importador)
    assert pode_autotriar(rig, importador, reg) is False


def test_gate_so_o_importador(proj_anco, importador, outro):
    reg = _reg_da_base(proj_anco, importador)
    assert pode_autotriar(proj_anco, importador, reg) is True
    assert pode_autotriar(proj_anco, outro, reg) is False


def test_curador_pode_autotriar_qualquer(proj_anco, importador):
    # is_staff satisfaz `eh_curador_no` (curador global/admin).
    curador = User.objects.create_user(
        username="cur",
        email="cur@u.edu",
        password="x",
        papel=User.Papel.CURADOR,
        is_staff=True,
    )
    reg = _reg_da_base(proj_anco, importador)
    assert pode_autotriar(proj_anco, curador, reg) is True


def test_incluir_consolida_e_promove(proj_anco, importador):
    reg = _reg_da_base(proj_anco, importador, titulo="Cognitive analysis of X")
    novo = autotriar(reg, RegistroTriagem.Decisao.INCLUIR, por=importador)
    reg.refresh_from_db()
    assert novo == RegistroTriagem.Status.INCLUIDO
    assert reg.status == RegistroTriagem.Status.INCLUIDO
    assert reg.artigo_id is not None  # promovido ao acervo
    assert reg.relevancia_score == 1  # casou com "cognitive analysis"
    # Um único parecer registrado.
    assert DecisaoTriagem.objects.filter(registro=reg, concluido_em__isnull=False).count() == 1


def test_excluir_consolida_com_motivo(proj_anco, importador):
    reg = _reg_da_base(proj_anco, importador)
    novo = autotriar(reg, RegistroTriagem.Decisao.EXCLUIR, por=importador, motivo="fora do escopo")
    reg.refresh_from_db()
    assert novo == RegistroTriagem.Status.EXCLUIDO
    assert reg.status == RegistroTriagem.Status.EXCLUIDO
    assert reg.artigo_id is None
    assert "fora do escopo" in reg.motivo_exclusao


def test_lista_para_autotriar_so_minhas_bases(proj_anco, importador, outro):
    meu = _reg_da_base(proj_anco, importador, doi="10/meu")
    _reg_da_base(proj_anco, outro, doi="10/seu")
    ids = set(registros_para_autotriar(proj_anco, importador).values_list("pk", flat=True))
    assert ids == {meu.pk}


def test_reverter_inclusao_exclui_e_apaga_artigo_orfao(proj_anco, importador):
    from apps.acervo.models import Artigo
    from apps.triagem.autotriagem import reverter_inclusao

    reg = _reg_da_base(proj_anco, importador, doi="10/rev")
    autotriar(reg, RegistroTriagem.Decisao.INCLUIR, por=importador)
    reg.refresh_from_db()
    art_pk = reg.artigo_id
    assert art_pk is not None

    ok = reverter_inclusao(reg, por=importador, motivo="erro de inclusão")
    reg.refresh_from_db()
    assert ok is True
    assert reg.status == RegistroTriagem.Status.EXCLUIDO
    assert reg.artigo_id is None
    assert "erro de inclusão" in reg.motivo_exclusao
    assert not Artigo.objects.filter(pk=art_pk).exists()  # artigo órfão removido


def test_reverter_inclusao_preserva_artigo_com_analise(proj_anco, importador):
    from apps.acervo.models import Analise, Artigo
    from apps.triagem.autotriagem import reverter_inclusao

    reg = _reg_da_base(proj_anco, importador, doi="10/rev2")
    autotriar(reg, RegistroTriagem.Decisao.INCLUIR, por=importador)
    reg.refresh_from_db()
    art_pk = reg.artigo_id
    Analise.objects.create(artigo_id=art_pk, analista=importador)  # já tem análise

    reverter_inclusao(reg, por=importador)
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.EXCLUIDO
    assert reg.artigo_id is None  # desvinculado do registro
    assert Artigo.objects.filter(pk=art_pk).exists()  # mas o artigo (com análise) fica
