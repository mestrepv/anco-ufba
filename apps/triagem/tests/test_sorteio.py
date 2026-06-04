"""Fase 9.3 — sorteio de revisores, avaliação (consenso/divergência) e signals."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem.aprovacao import avaliar_apos_triagem, registros_para_desempate
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.sorteio import executar_sorteio, revisores_elegiveis

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


def _revisor(n):
    return User.objects.create_user(
        username=f"rev{n}", email=f"rev{n}@u.edu", password="x",
        papel=User.Papel.ANALISTA, revisor_aprovado=True, aceita_revisoes=True,
    )


@pytest.fixture
def revisores(db):
    return [_revisor(i) for i in range(4)]


@pytest.fixture
def registro(db, protocolo):
    return RegistroTriagem.objects.create(protocolo=protocolo, titulo="T", doi="10.1/a")


# ---- elegibilidade / sorteio ----------------------------------------------

def test_sorteia_n_revisores(protocolo, registro, revisores):
    res = executar_sorteio(registro)
    assert res.criadas == protocolo.n_revisores  # 2
    registro.refresh_from_db()
    assert registro.status == RegistroTriagem.Status.EM_TRIAGEM
    assert DecisaoTriagem.objects.filter(registro=registro).count() == 2


def test_sorteio_exclui_coletor(protocolo, registro, revisores):
    # um dos revisores rodou a busca de origem → não pode triar
    coletor = revisores[0]
    b = Busca.objects.create(protocolo=protocolo, criado_por=coletor)
    registro.origem_buscas.add(b)
    elegiveis = set(revisores_elegiveis(registro))
    assert coletor not in elegiveis


def test_sorteio_ja_no_acervo_nao_tria(protocolo, revisores):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="X", doi="10.1/x", ja_no_acervo=True
    )
    res = executar_sorteio(reg)
    assert res.criadas == 0
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.IDENTIFICADO


def test_sorteio_idempotente(protocolo, registro, revisores):
    executar_sorteio(registro)
    res2 = executar_sorteio(registro)
    assert res2.criadas == 0
    assert DecisaoTriagem.objects.filter(registro=registro).count() == 2


def test_revisores_insuficientes_fila(protocolo, registro):
    so_um = _revisor(99)  # noqa: F841 — único revisor aprovado
    res = executar_sorteio(registro)
    assert res.fila_de_espera is True and res.criadas == 0
    registro.refresh_from_db()
    assert registro.status == RegistroTriagem.Status.IDENTIFICADO


# ---- avaliação: consenso / divergência ------------------------------------

def _decidir(registro, revisor, decisao, motivo=""):
    d = DecisaoTriagem.objects.get(registro=registro, revisor=revisor)
    d.decisao = decisao
    d.motivo_exclusao = motivo
    d.concluido_em = timezone.now()
    d.save()
    return d


def test_consenso_incluir(protocolo, registro, revisores):
    executar_sorteio(registro)
    for d in DecisaoTriagem.objects.filter(registro=registro):
        _decidir(registro, d.revisor, RegistroTriagem.Decisao.INCLUIR)
    registro.refresh_from_db()  # signal avaliou via sync
    assert registro.status == RegistroTriagem.Status.INCLUIDO
    assert registro.decisao_final == RegistroTriagem.Decisao.INCLUIR


def test_consenso_excluir_agrega_motivo(protocolo, registro, revisores):
    executar_sorteio(registro)
    for i, d in enumerate(DecisaoTriagem.objects.filter(registro=registro)):
        _decidir(registro, d.revisor, RegistroTriagem.Decisao.EXCLUIR, f"motivo{i}")
    registro.refresh_from_db()
    assert registro.status == RegistroTriagem.Status.EXCLUIDO
    assert "motivo" in registro.motivo_exclusao


def test_divergencia_aguarda_desempate(protocolo, registro, revisores):
    executar_sorteio(registro)
    decisoes = list(DecisaoTriagem.objects.filter(registro=registro))
    _decidir(registro, decisoes[0].revisor, RegistroTriagem.Decisao.INCLUIR)
    _decidir(registro, decisoes[1].revisor, RegistroTriagem.Decisao.EXCLUIR)
    registro.refresh_from_db()
    assert registro.status == RegistroTriagem.Status.EM_TRIAGEM  # não decidiu
    assert registro in registros_para_desempate(protocolo)


def test_avaliacao_espera_todas_decisoes(protocolo, registro, revisores):
    executar_sorteio(registro)
    primeira = DecisaoTriagem.objects.filter(registro=registro).first()
    _decidir(registro, primeira.revisor, RegistroTriagem.Decisao.INCLUIR)
    # falta a segunda → não decide
    res = avaliar_apos_triagem(registro)
    assert res.decidida is False
    registro.refresh_from_db()
    assert registro.status == RegistroTriagem.Status.EM_TRIAGEM
