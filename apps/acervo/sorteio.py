"""
Sorteio de revisores para uma Analise submetida.

Regras (spec secao 5.3):
- Sempre 2 revisores estruturais (prazo +14 dias).
- Se a Analise tem resenha critica: +2 revisores cegos (prazo +21 dias),
  distintos dos estruturais.
- Excluir o autor da analise.
- Excluir analistas com OUTRA analise do mesmo artigo (preserva
  independencia entre analises do mesmo artigo).
- Respeitar `aceita_revisoes=True` e `limite_revisoes_simultaneas`.
- Se nao houver revisores suficientes: registrar fila de espera (flag
  visivel para curadores) e nao criar revisoes a menos.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Analise, Revisao

logger = logging.getLogger(__name__)
User = get_user_model()

PRAZO_ESTRUTURAL_DIAS = 14
PRAZO_CEGA_DIAS = 21
N_REVISORES_ESTRUTURAIS = 2
N_REVISORES_CEGOS = 2


@dataclass
class ResultadoSorteio:
    """Resumo do sorteio. `fila_de_espera=True` indica revisores insuficientes."""

    estruturais_criadas: int
    cegas_criadas: int
    fila_de_espera: bool
    motivo: str = ""


def revisores_elegiveis(analise: Analise, excluir_ids: set[int] | None = None):
    """
    Devolve queryset de Users elegiveis a revisar `analise`.

    Aplica todas as exclusoes da spec:
    - papel in {analista, curador}
    - is_active=True
    - aceita_revisoes=True
    - menos que limite_revisoes_simultaneas revisoes pendentes
    - nao eh autor da analise
    - nao tem outra analise (em qualquer status nao-rejeitado) do mesmo artigo
    - nao esta em `excluir_ids` (revisores ja sorteados nesta passada)
    """
    excluir_ids = excluir_ids or set()

    # Analistas que tem outra analise do mesmo artigo
    autores_outras_analises = (
        Analise.objects.filter(artigo=analise.artigo)
        .exclude(pk=analise.pk)
        .values_list("analista_id", flat=True)
    )

    # Conta revisoes pendentes por revisor
    qs = (
        User.objects.filter(
            papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
            is_active=True,
            aceita_revisoes=True,
        )
        .exclude(pk=analise.analista_id)
        .exclude(pk__in=autores_outras_analises)
        .exclude(pk__in=excluir_ids)
        .annotate(
            revisoes_pendentes=Count(
                "revisoes_feitas",
                filter=Q(revisoes_feitas__concluido_em__isnull=True),
            )
        )
        .filter(revisoes_pendentes__lt=F("limite_revisoes_simultaneas"))
    )
    return qs


def _sortear_n(elegiveis_qs, n: int) -> list:
    """Sorteia ate `n` Users distintos do queryset (ordem aleatoria)."""
    candidatos = list(elegiveis_qs)
    if not candidatos:
        return []
    random.shuffle(candidatos)
    return candidatos[:n]


@transaction.atomic
def executar_sorteio(analise: Analise) -> ResultadoSorteio:
    """
    Executa o sorteio para uma Analise no status `submetida`.

    Idempotente: se ja existem revisoes para a analise, nao recria.
    Se faltarem revisores, marca fila_de_espera e mantem analise no
    status `submetida`. Se OK, muda para `em_revisao`.
    """
    if Revisao.objects.filter(analise=analise).exists():
        logger.info("Sorteio ja executado para analise %s — skip", analise.pk)
        return ResultadoSorteio(
            estruturais_criadas=0,
            cegas_criadas=0,
            fila_de_espera=False,
            motivo="Sorteio ja executado anteriormente.",
        )

    # 1. Sorteio estrutural
    elegiveis_estruturais = revisores_elegiveis(analise)
    estruturais = _sortear_n(elegiveis_estruturais, N_REVISORES_ESTRUTURAIS)

    if len(estruturais) < N_REVISORES_ESTRUTURAIS:
        logger.warning(
            "Faltam revisores estruturais para analise %s (%d de %d disponiveis)",
            analise.pk,
            len(estruturais),
            N_REVISORES_ESTRUTURAIS,
        )
        return ResultadoSorteio(
            estruturais_criadas=0,
            cegas_criadas=0,
            fila_de_espera=True,
            motivo=(
                f"Revisores estruturais insuficientes "
                f"({len(estruturais)} de {N_REVISORES_ESTRUTURAIS})."
            ),
        )

    # 2. Sorteio cego (se aplicavel)
    cegos = []
    if analise.tem_resenha:
        excluir = {u.pk for u in estruturais}
        elegiveis_cegos = revisores_elegiveis(analise, excluir_ids=excluir)
        cegos = _sortear_n(elegiveis_cegos, N_REVISORES_CEGOS)
        if len(cegos) < N_REVISORES_CEGOS:
            logger.warning(
                "Faltam revisores cegos para analise %s (%d de %d)",
                analise.pk,
                len(cegos),
                N_REVISORES_CEGOS,
            )
            return ResultadoSorteio(
                estruturais_criadas=0,
                cegas_criadas=0,
                fila_de_espera=True,
                motivo=(f"Revisores cegos insuficientes ({len(cegos)} de {N_REVISORES_CEGOS})."),
            )

    # 3. Persiste revisoes
    agora = timezone.now()
    for revisor in estruturais:
        Revisao.objects.create(
            analise=analise,
            revisor=revisor,
            tipo=Revisao.Tipo.ESTRUTURAL,
            prazo_em=agora + timedelta(days=PRAZO_ESTRUTURAL_DIAS),
        )
    for revisor in cegos:
        Revisao.objects.create(
            analise=analise,
            revisor=revisor,
            tipo=Revisao.Tipo.CEGA,
            prazo_em=agora + timedelta(days=PRAZO_CEGA_DIAS),
        )

    # 4. Status: submetida -> em_revisao
    analise.status = Analise.Status.EM_REVISAO
    analise.save(update_fields=["status"])

    return ResultadoSorteio(
        estruturais_criadas=len(estruturais),
        cegas_criadas=len(cegos),
        fila_de_espera=False,
    )


@transaction.atomic
def re_sortear_revisao_expirada(revisao: Revisao) -> Revisao | None:
    """
    Substitui um revisor expirado por outro elegivel.

    Mantem a Revisao original com `concluido_em=None` mas troca o `revisor`
    e estende o `prazo_em`. Se nao houver substituto, retorna None e a
    revisao continua expirada (fila de espera implicita).
    """
    if revisao.concluido_em is not None:
        return revisao  # ja concluida, nada a fazer

    # Excluir revisores ja designados nesta analise (do mesmo tipo ou nao)
    ja_designados = set(
        Revisao.objects.filter(analise=revisao.analise).values_list("revisor_id", flat=True)
    )
    elegiveis = revisores_elegiveis(revisao.analise, excluir_ids=ja_designados)
    novos = _sortear_n(elegiveis, 1)
    if not novos:
        logger.warning("Sem substituto para revisao %s", revisao.pk)
        return None

    prazo_dias = (
        PRAZO_ESTRUTURAL_DIAS if revisao.tipo == Revisao.Tipo.ESTRUTURAL else PRAZO_CEGA_DIAS
    )
    revisao.revisor = novos[0]
    revisao.prazo_em = timezone.now() + timedelta(days=prazo_dias)
    revisao.save(update_fields=["revisor", "prazo_em"])
    return revisao


def revisoes_expiradas():
    """Queryset de revisoes com prazo_em < agora e concluido_em IS NULL."""
    return Revisao.objects.filter(
        prazo_em__lt=timezone.now(),
        concluido_em__isnull=True,
    )
