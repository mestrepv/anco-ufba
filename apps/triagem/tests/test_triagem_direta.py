"""Triagem direta (sem sorteio): atribuição determinística + reúso do downstream."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem.aprovacao import registros_para_desempate
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.triagem_direta import atribuir_triagem_direta, revisores_validos

from .conftest import inscrever

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


def _user(n, **extra):
    return User.objects.create_user(
        username=f"u{n}", email=f"u{n}@u.edu", password="x",
        papel=User.Papel.ANALISTA, **extra,
    )


@pytest.fixture
def dois_revisores(db, protocolo):
    revs = [_user(1), _user(2)]
    inscrever(protocolo, *revs)
    return revs


@pytest.fixture
def registros(db, protocolo):
    return [
        RegistroTriagem.objects.create(protocolo=protocolo, titulo=f"T{i}", doi=f"10.1/{i}")
        for i in range(3)
    ]


# ---- atribuição -----------------------------------------------------------


def test_atribui_todos_revisores_a_todos_registros(protocolo, registros, dois_revisores):
    res = atribuir_triagem_direta(protocolo, dois_revisores)
    assert res.registros == 3
    assert res.decisoes == 6  # 3 registros × 2 revisores
    for r in registros:
        r.refresh_from_db()
        assert r.status == RegistroTriagem.Status.EM_TRIAGEM
        assert DecisaoTriagem.objects.filter(registro=r).count() == 2


def test_nao_exige_sorteio_nem_independencia(protocolo, registros, dois_revisores):
    # O coletor da busca pode triar (ao contrário do sorteio) e não precisa
    # de revisor_aprovado/aceita_revisoes.
    coletor = dois_revisores[0]
    assert coletor.revisor_aprovado is False
    b = Busca.objects.create(protocolo=protocolo, criado_por=coletor)
    registros[0].origem_buscas.add(b)
    atribuir_triagem_direta(protocolo, dois_revisores)
    assert DecisaoTriagem.objects.filter(registro=registros[0], revisor=coletor).exists()


def test_ignora_ja_no_acervo(protocolo, dois_revisores):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="X", doi="10.1/x", ja_no_acervo=True
    )
    atribuir_triagem_direta(protocolo, dois_revisores)
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.IDENTIFICADO
    assert DecisaoTriagem.objects.filter(registro=reg).count() == 0


def test_idempotente(protocolo, registros, dois_revisores):
    atribuir_triagem_direta(protocolo, dois_revisores)
    res2 = atribuir_triagem_direta(protocolo, dois_revisores)
    assert res2.decisoes == 0
    assert DecisaoTriagem.objects.count() == 6


def test_adicionar_revisor_depois_so_em_aberto(protocolo, registros, dois_revisores):
    # 1ª rodada só com o revisor A; registros ficam em_triagem com 1 decisão.
    rev_a, rev_b = dois_revisores
    atribuir_triagem_direta(protocolo, [rev_a])
    assert DecisaoTriagem.objects.filter(revisor=rev_a).count() == 3
    # Adiciona B depois: rodar de novo NÃO pega registros que já saíram de
    # 'identificado' (estão em_triagem) — comportamento esperado/avisado na UI.
    res = atribuir_triagem_direta(protocolo, [rev_a, rev_b])
    assert res.registros == 0
    assert DecisaoTriagem.objects.filter(revisor=rev_b).count() == 0


def test_sem_revisores_nao_faz_nada(protocolo, registros):
    res = atribuir_triagem_direta(protocolo, [])
    assert res.registros == 0 and res.decisoes == 0
    assert not DecisaoTriagem.objects.exists()


def test_revisores_validos_filtra_nao_membros(protocolo, dois_revisores):
    estranho = _user(99)  # não inscrito no projeto
    ids = [dois_revisores[0].id, estranho.id, dois_revisores[1].id]
    validos = revisores_validos(protocolo, ids)
    assert estranho not in validos
    assert set(validos) == set(dois_revisores)


# ---- downstream (consenso/desempate) já funciona --------------------------


def _decidir(registro, revisor, decisao):
    d = DecisaoTriagem.objects.get(registro=registro, revisor=revisor)
    d.decisao = decisao
    d.concluido_em = timezone.now()
    d.save()


def test_consenso_incluir_apos_triagem_direta(protocolo, registros, dois_revisores):
    atribuir_triagem_direta(protocolo, dois_revisores)
    reg = registros[0]
    for rev in dois_revisores:
        _decidir(reg, rev, RegistroTriagem.Decisao.INCLUIR)
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.INCLUIDO


def test_divergencia_vai_para_desempate(protocolo, registros, dois_revisores):
    atribuir_triagem_direta(protocolo, dois_revisores)
    reg = registros[0]
    _decidir(reg, dois_revisores[0], RegistroTriagem.Decisao.INCLUIR)
    _decidir(reg, dois_revisores[1], RegistroTriagem.Decisao.EXCLUIR)
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.EM_TRIAGEM
    assert reg in registros_para_desempate(protocolo)
