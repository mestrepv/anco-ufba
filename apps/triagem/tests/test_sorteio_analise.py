"""Fase 13 — sorteio da análise: cota, diversidade de base, única/dupla."""

import pytest
from django.contrib.auth import get_user_model

from apps.acervo.models import Analise
from apps.triagem.models import (
    AtribuicaoAnalise,
    ProtocoloTriagem,
    RegistroTriagem,
    SorteioAnalise,
)
from apps.triagem.promocao import promover_para_acervo
from apps.triagem.sorteio_analise import _pool, desfazer_sorteio, executar_sorteio_analise

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def proj(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


def _analista(proj, nome):
    return membro(
        User.objects.create_user(
            username=nome,
            email=f"{nome}@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
        )
    )


_seq = iter(range(1, 10_000))


def _incluido(proj, base, score, ano=2020):
    n = next(_seq)
    reg = RegistroTriagem.objects.create(
        protocolo=proj,
        titulo=f"Art {n}",
        doi=f"10/{n}",
        ano=ano,
        status=RegistroTriagem.Status.INCLUIDO,
        relevancia_score=score,
    )
    art = promover_para_acervo(reg)
    art.base_consulta = None
    art.outra_base_consulta = base
    art.save(update_fields=["base_consulta", "outra_base_consulta"])
    return reg, art


def test_cota_e_total(proj):
    a1 = _analista(proj, "a1")
    for i in range(8):
        _incluido(proj, base=f"B{i}", score=i)
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    assert res.atribuidas == 5  # cota respeitada, mesmo com 8 disponíveis
    assert AtribuicaoAnalise.objects.filter(sorteio=res.sorteio, analista=a1).count() == 5


def test_prioriza_relevancia(proj):
    a1 = _analista(proj, "a1")
    altos = [_incluido(proj, base=f"H{i}", score=100 + i)[1].pk for i in range(5)]
    for i in range(5):
        _incluido(proj, base=f"L{i}", score=1)
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    escolhidos = set(
        AtribuicaoAnalise.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert escolhidos == set(altos)  # os 5 mais relevantes


def test_diversidade_preferida_mas_nao_obrigatoria(proj):
    """Pool só tem 2 bases; a cota de 5 ainda é preenchida (diversidade não bloqueia)."""
    a1 = _analista(proj, "a1")
    for _ in range(3):
        _incluido(proj, base="BaseX", score=10)
    for _ in range(3):
        _incluido(proj, base="BaseY", score=10)
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    assert res.atribuidas == 5  # não travou por causa da base repetida


def test_dupla_dois_analistas_distintos(proj):
    a1, a2 = _analista(proj, "a1"), _analista(proj, "a2")
    arts = [_incluido(proj, base=f"B{i}", score=10)[1] for i in range(5)]
    res = executar_sorteio_analise(
        proj,
        modo_revisao=SorteioAnalise.ModoRevisao.DUPLA,
        cota=5,
        por=a1,
        analistas=[a1, a2],
    )
    # cada artigo tem 2 assentos → 5 artigos atendem a cota de 2 analistas (10 atribuições)
    assert res.atribuidas == 10
    for art in arts:
        analistas = set(
            AtribuicaoAnalise.objects.filter(sorteio=res.sorteio, artigo=art).values_list(
                "analista_id", flat=True
            )
        )
        assert analistas == {a1.id, a2.id}  # dois distintos


def test_nao_atribui_artigo_ja_analisado(proj):
    a1 = _analista(proj, "a1")
    reg, art = _incluido(proj, base="B0", score=50)
    Analise.objects.create(artigo=art, analista=a1)  # já analisou
    outros = [_incluido(proj, base=f"B{i}", score=10)[1].pk for i in range(1, 6)]
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    escolhidos = set(
        AtribuicaoAnalise.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert art.pk not in escolhidos
    assert escolhidos == set(outros)


def test_idempotente_nao_realoca(proj):
    a1 = _analista(proj, "a1")
    for i in range(5):
        _incluido(proj, base=f"B{i}", score=10)
    r1 = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    r2 = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    assert r1.atribuidas == 5
    assert r2.sorteio is None  # nada novo a sortear
    assert "Nenhum artigo" in r2.motivo


def test_faltas_quando_pool_insuficiente(proj):
    a1 = _analista(proj, "a1")
    for i in range(2):
        _incluido(proj, base=f"B{i}", score=10)
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1])
    assert res.atribuidas == 2
    assert res.faltas[a1.id] == 3  # faltou 3 da cota — registrado, não silencioso


def test_sem_analistas(proj):
    _incluido(proj, base="B0", score=10)
    res = executar_sorteio_analise(proj, cota=5, analistas=[])
    assert res.sorteio is None
    assert "analista" in res.motivo.lower()


# ── Só artigos completos + desfazer sorteio ─────────────────────────────────


def _incluido_completo(proj, n, *, completo):
    reg = RegistroTriagem.objects.create(
        protocolo=proj,
        titulo=f"C{n}",
        doi=f"10/c{n}",
        resumo="um resumo" if completo else "",
        palavras_chaves="cognição" if completo else "",
        ano=2020,
        status=RegistroTriagem.Status.INCLUIDO,
        identificador=f"c{n}",
    )
    return reg, promover_para_acervo(reg)


def test_exigir_completos_so_inclui_completos(proj):
    a1 = _analista(proj, "ac")
    completos = {_incluido_completo(proj, i, completo=True)[1].pk for i in range(3)}
    for i in range(3, 6):
        _incluido_completo(proj, i, completo=False)  # sem resumo/palavras-chave
    res = executar_sorteio_analise(
        proj, cota=10, por=a1, analistas=[a1], aleatorio=True, exigir_completos=True
    )
    escolhidos = set(
        AtribuicaoAnalise.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert escolhidos == completos  # só os 3 completos entraram


def test_exigir_completos_sem_nenhum_completo(proj):
    a1 = _analista(proj, "ac2")
    _incluido_completo(proj, 0, completo=False)
    res = executar_sorteio_analise(
        proj, cota=5, por=a1, analistas=[a1], aleatorio=True, exigir_completos=True
    )
    assert res.sorteio is None
    assert "completo" in res.motivo.lower()


def test_desfazer_sorteio_remove_atribuicoes(proj):
    a1 = _analista(proj, "ad")
    for i in range(3):
        _incluido_completo(proj, i, completo=True)
    res = executar_sorteio_analise(
        proj, cota=5, por=a1, analistas=[a1], aleatorio=True, exigir_completos=True
    )
    sid = res.sorteio.pk
    assert AtribuicaoAnalise.objects.filter(sorteio_id=sid).count() == 3
    n = desfazer_sorteio(res.sorteio)
    assert n == 3
    assert not SorteioAnalise.objects.filter(pk=sid).exists()
    assert AtribuicaoAnalise.objects.filter(sorteio_id=sid).count() == 0
    # Artigos voltam ao pool: novo sorteio os pega de novo.
    res2 = executar_sorteio_analise(
        proj, cota=5, por=a1, analistas=[a1], aleatorio=True, exigir_completos=True
    )
    assert res2.atribuidas == 3


# ── Sorteio aleatório (modo ANCO simplificado) ──────────────────────────────


def test_aleatorio_segue_ordem_embaralhada_e_grava_semente(proj):
    """Com a seed fixa, a seleção é o prefixo do pool embaralhado — reprodutível."""
    a1 = _analista(proj, "ar1")
    for i in range(10):
        _incluido(proj, base=f"B{i}", score=i)
    pool = _pool(proj, set(), aleatorio=True, semente=99)
    esperado = {item.artigo_id for item in pool[:5]}
    res = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1], aleatorio=True, semente=99)
    obtido = set(
        AtribuicaoAnalise.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert obtido == esperado
    res.sorteio.refresh_from_db()
    assert res.sorteio.semente == 99  # seed registrada para auditoria


def test_aleatorio_ignora_relevancia(proj):
    """O sorteio aleatório não escolhe necessariamente os mais relevantes."""
    a1 = _analista(proj, "ar2")
    altos = {_incluido(proj, base=f"H{i}", score=100 + i)[1].pk for i in range(5)}
    for i in range(5):
        _incluido(proj, base=f"L{i}", score=1)
    # Procura uma seed (determinística) cuja seleção difira dos 5 mais relevantes.
    seed = next(
        s
        for s in range(1, 200)
        if {item.artigo_id for item in _pool(proj, set(), aleatorio=True, semente=s)[:5]} != altos
    )
    res = executar_sorteio_analise(
        proj, cota=5, por=a1, analistas=[a1], aleatorio=True, semente=seed
    )
    obtido = set(
        AtribuicaoAnalise.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert obtido != altos  # não é a seleção determinística por relevância


def test_aleatorio_respeita_cota_e_idempotencia(proj):
    a1 = _analista(proj, "ar3")
    for i in range(8):
        _incluido(proj, base=f"B{i}", score=10)
    r1 = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1], aleatorio=True)
    assert r1.atribuidas == 5
    assert r1.sorteio.semente is not None  # seed gerada automaticamente
    r2 = executar_sorteio_analise(proj, cota=5, por=a1, analistas=[a1], aleatorio=True)
    # 3 restantes no pool → completa a cota anterior só até o disponível.
    novos = AtribuicaoAnalise.objects.filter(sorteio=r2.sorteio).count() if r2.sorteio else 0
    assert novos == 3  # não realoca os 5 já distribuídos
