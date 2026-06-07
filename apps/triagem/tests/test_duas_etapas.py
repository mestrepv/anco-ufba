"""Fase 11.4 — triagem em duas etapas (título/resumo → texto completo).

A 2ª etapa é **opt-in** via `protocolo.usa_texto_completo`. Os testes cobrem:
ambos os comportamentos (etapa única preservada e duas etapas), incluindo o
sorteio do 2º estágio disparado pelo consenso, a exclusão com motivo no texto
completo, o desempate por etapa e as contagens PRISMA.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem import prisma
from apps.triagem.aprovacao import consolidar_registro, destino, etapa_atual
from apps.triagem.models import DecisaoTriagem, ProtocoloTriagem, RegistroTriagem
from apps.triagem.sorteio import executar_sorteio

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db

St = RegistroTriagem.Status
Dec = RegistroTriagem.Decisao
Et = DecisaoTriagem.Etapa


def _revisor(n):
    return membro(
        User.objects.create_user(
            username=f"rev{n}",
            email=f"rev{n}@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
            aceita_revisoes=True,
        )
    )


@pytest.fixture
def revisores(db):
    return [_revisor(i) for i in range(5)]


@pytest.fixture
def protocolo_2etapas(db):
    p = ProtocoloTriagem.ativo()
    p.usa_texto_completo = True
    p.save(update_fields=["usa_texto_completo"])
    return p


def _decidir_etapa(registro, etapa, decisao, motivo=""):
    """Conclui todas as decisões abertas da etapa com a mesma decisão."""
    for d in DecisaoTriagem.objects.filter(
        registro=registro, etapa=etapa, concluido_em__isnull=True
    ):
        d.decisao = decisao
        d.motivo_exclusao = motivo
        d.concluido_em = timezone.now()
        d.save()  # signal avalia via sync


# ── destino() puro ─────────────────────────────────────────────────────────


def test_destino_etapa_unica(db):
    p = ProtocoloTriagem.ativo()  # usa_texto_completo=False
    r = RegistroTriagem(protocolo=p, status=St.EM_TRIAGEM)
    assert destino(r, Dec.INCLUIR) == St.INCLUIDO
    assert destino(r, Dec.EXCLUIR) == St.EXCLUIDO


def test_destino_duas_etapas(protocolo_2etapas):
    r = RegistroTriagem(protocolo=protocolo_2etapas, status=St.EM_TRIAGEM)
    assert destino(r, Dec.INCLUIR) == St.INCLUIDO_TA  # vai ao texto completo
    assert destino(r, Dec.EXCLUIR) == St.EXCLUIDO
    r.status = St.EM_TEXTO
    assert destino(r, Dec.INCLUIR) == St.INCLUIDO
    assert destino(r, Dec.EXCLUIR) == St.EXCLUIDO_TC


# ── fluxo completo de 2 etapas ─────────────────────────────────────────────


def test_consenso_ta_dispara_texto_completo(protocolo_2etapas, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="T", doi="10.1/a")
    executar_sorteio(reg, Et.TITULO_RESUMO)
    assert DecisaoTriagem.objects.filter(registro=reg, etapa=Et.TITULO_RESUMO).count() == 2

    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.INCLUIR)
    reg.refresh_from_db()
    # Não vira INCLUIDO direto: passa ao 2º estágio (sorteado automaticamente).
    assert reg.status == St.EM_TEXTO
    assert reg.artigo_id is None
    assert DecisaoTriagem.objects.filter(registro=reg, etapa=Et.TEXTO_COMPLETO).count() == 2


def test_fluxo_completo_incluido_promove(protocolo_2etapas, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="T", doi="10.1/b")
    executar_sorteio(reg, Et.TITULO_RESUMO)
    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.INCLUIR)
    _decidir_etapa(reg, Et.TEXTO_COMPLETO, Dec.INCLUIR)
    reg.refresh_from_db()
    assert reg.status == St.INCLUIDO
    assert reg.decisao_final == Dec.INCLUIR
    assert reg.artigo_id is not None  # promovido ao acervo


def test_excluido_no_texto_completo_guarda_motivo(protocolo_2etapas, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="T", doi="10.1/c")
    executar_sorteio(reg, Et.TITULO_RESUMO)
    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.INCLUIR)
    _decidir_etapa(reg, Et.TEXTO_COMPLETO, Dec.EXCLUIR, motivo="sem dados de cognição")
    reg.refresh_from_db()
    assert reg.status == St.EXCLUIDO_TC
    assert reg.artigo_id is None  # não promove
    assert "cognição" in reg.motivo_exclusao


def test_excluido_no_ta_nao_vai_ao_texto(protocolo_2etapas, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="T", doi="10.1/d")
    executar_sorteio(reg, Et.TITULO_RESUMO)
    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.EXCLUIR, motivo="fora de escopo")
    reg.refresh_from_db()
    assert reg.status == St.EXCLUIDO
    assert DecisaoTriagem.objects.filter(registro=reg, etapa=Et.TEXTO_COMPLETO).count() == 0


def test_etapa_unica_inalterada(revisores):
    """Sem usa_texto_completo, consenso incluir vai direto a INCLUIDO."""
    p = ProtocoloTriagem.ativo()
    reg = RegistroTriagem.objects.create(protocolo=p, titulo="T", doi="10.1/e")
    executar_sorteio(reg)
    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.INCLUIR)
    reg.refresh_from_db()
    assert reg.status == St.INCLUIDO
    assert reg.artigo_id is not None


# ── desempate por etapa ────────────────────────────────────────────────────


def test_desempate_texto_completo(protocolo_2etapas, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="T", doi="10.1/f")
    executar_sorteio(reg, Et.TITULO_RESUMO)
    _decidir_etapa(reg, Et.TITULO_RESUMO, Dec.INCLUIR)
    reg.refresh_from_db()
    assert reg.status == St.EM_TEXTO

    # Divergência no texto: um inclui, outro exclui.
    decs = list(DecisaoTriagem.objects.filter(registro=reg, etapa=Et.TEXTO_COMPLETO))
    for d, escolha in zip(decs, [Dec.INCLUIR, Dec.EXCLUIR], strict=True):
        d.decisao = escolha
        d.concluido_em = timezone.now()
        d.save()
    reg.refresh_from_db()
    assert reg.status == St.EM_TEXTO  # aguarda desempate

    from apps.triagem.aprovacao import registros_para_desempate

    assert reg in registros_para_desempate(protocolo_2etapas)

    # Curador desempata por incluir → consolida e promove.
    consolidar_registro(reg, Dec.INCLUIR, por=revisores[0])
    reg.refresh_from_db()
    assert reg.status == St.INCLUIDO


def test_etapa_atual(protocolo_2etapas):
    r = RegistroTriagem(protocolo=protocolo_2etapas, status=St.EM_TRIAGEM)
    assert etapa_atual(r) == Et.TITULO_RESUMO
    r.status = St.EM_TEXTO
    assert etapa_atual(r) == Et.TEXTO_COMPLETO


# ── PRISMA com duas etapas ─────────────────────────────────────────────────


def test_prisma_conta_segundo_estagio(protocolo_2etapas, revisores):
    incluido = RegistroTriagem.objects.create(protocolo=protocolo_2etapas, titulo="A", doi="10.1/g")
    executar_sorteio(incluido, Et.TITULO_RESUMO)
    _decidir_etapa(incluido, Et.TITULO_RESUMO, Dec.INCLUIR)
    _decidir_etapa(incluido, Et.TEXTO_COMPLETO, Dec.EXCLUIR, motivo="texto não elegível")

    c = prisma.computar(protocolo_2etapas)
    assert c.duas_etapas is True
    assert c.excluidos_tc == 1
    # Motivo consolidado junta os pareceres dos revisores (PRISMA: com razões).
    assert "texto não elegível" in c.excluidos_tc_por_motivo[0]["motivo_exclusao"]
