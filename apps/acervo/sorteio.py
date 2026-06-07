"""
Sorteio de revisores cegos para uma Resenha crítica submetida.

A revisão por pares vale APENAS para resenhas críticas (a análise em si é
publicada por aprovação de curador, sem revisão por pares).

Regras:
- Sorteia N revisores cegos (autoria mascarada), prazo +21 dias.
- Exclui o autor da resenha (= autor da análise).
- Exclui analistas com OUTRA análise do mesmo artigo (preserva
  independência entre análises do mesmo artigo).
- Respeita `aceita_revisoes=True`, `revisor_aprovado=True` e
  `limite_revisoes_simultaneas`.
- Se não houver revisores suficientes: registra fila de espera e não cria
  revisões a menos.
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

from .models import Analise, Resenha, Revisao

logger = logging.getLogger(__name__)
User = get_user_model()

PRAZO_CEGA_DIAS = 21
N_REVISORES_CEGOS = 2


@dataclass
class ResultadoSorteio:
    """Resumo do sorteio. `fila_de_espera=True` indica revisores insuficientes."""

    cegas_criadas: int
    fila_de_espera: bool
    motivo: str = ""


def revisores_elegiveis(resenha: Resenha, excluir_ids: set[int] | None = None):
    """
    Devolve queryset de Users elegíveis a revisar `resenha`.

    Exclusões:
    - papel in {analista, curador}, is_active, aceita_revisoes, revisor_aprovado
    - menos que `limite_revisoes_simultaneas` revisões pendentes
    - não é autor da análise/resenha
    - não tem outra análise do mesmo artigo
    - não está em `excluir_ids` (já sorteados nesta passada)
    """
    excluir_ids = excluir_ids or set()
    analise = resenha.analise

    autores_outras_analises = (
        Analise.objects.filter(artigo=analise.artigo)
        .exclude(pk=analise.pk)
        .values_list("analista_id", flat=True)
    )

    qs = (
        User.objects.filter(
            papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
            is_active=True,
            aceita_revisoes=True,
            revisor_aprovado=True,
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
    """Sorteia até `n` Users distintos do queryset (ordem aleatória)."""
    candidatos = list(elegiveis_qs)
    if not candidatos:
        return []
    random.shuffle(candidatos)
    return candidatos[:n]


@transaction.atomic
def executar_sorteio(resenha: Resenha) -> ResultadoSorteio:
    """
    Sorteia revisores cegos para uma Resenha em `submetida`.

    Idempotente: não recria se já há ciclo cego pendente (Revisão com
    `concluido_em__isnull=True`). Exclui quem já revisou esta resenha antes
    (re-submissões pós-publicação). Se faltarem revisores, marca
    `fila_de_espera` e mantém a resenha em `submetida`. Se OK, vai para
    `em_revisao`.
    """
    pendentes = Revisao.objects.filter(resenha=resenha, concluido_em__isnull=True)
    if pendentes.exists():
        logger.info("Ciclo cego já pendente para resenha %s — skip", resenha.pk)
        return ResultadoSorteio(0, False, "Já existe ciclo cego pendente.")

    ja_revisaram = set(Revisao.objects.filter(resenha=resenha).values_list("revisor_id", flat=True))
    elegiveis = revisores_elegiveis(resenha, excluir_ids=ja_revisaram)
    cegos = _sortear_n(elegiveis, N_REVISORES_CEGOS)

    if len(cegos) < N_REVISORES_CEGOS:
        logger.warning(
            "Faltam revisores cegos para resenha %s (%d de %d disponíveis)",
            resenha.pk,
            len(cegos),
            N_REVISORES_CEGOS,
        )
        return ResultadoSorteio(
            0,
            True,
            f"Revisores cegos insuficientes ({len(cegos)} de {N_REVISORES_CEGOS}).",
        )

    agora = timezone.now()
    for revisor in cegos:
        Revisao.objects.create(
            resenha=resenha,
            revisor=revisor,
            prazo_em=agora + timedelta(days=PRAZO_CEGA_DIAS),
        )

    resenha.status = Resenha.Status.EM_REVISAO
    resenha.save(update_fields=["status"])

    return ResultadoSorteio(cegas_criadas=len(cegos), fila_de_espera=False)


@transaction.atomic
def re_sortear_revisao_expirada(revisao: Revisao) -> Revisao | None:
    """
    Substitui um revisor expirado por outro elegível na mesma resenha.

    Mantém a Revisao com `concluido_em=None`, troca o `revisor` e estende o
    `prazo_em`. Sem substituto, retorna None (fila de espera implícita).
    """
    if revisao.concluido_em is not None:
        return revisao
    if revisao.resenha_id is None:
        return None

    ja_designados = set(
        Revisao.objects.filter(resenha=revisao.resenha).values_list("revisor_id", flat=True)
    )
    elegiveis = revisores_elegiveis(revisao.resenha, excluir_ids=ja_designados)
    novos = _sortear_n(elegiveis, 1)
    if not novos:
        logger.warning("Sem substituto para revisão %s", revisao.pk)
        return None

    revisao.revisor = novos[0]
    revisao.prazo_em = timezone.now() + timedelta(days=PRAZO_CEGA_DIAS)
    revisao.save(update_fields=["revisor", "prazo_em"])
    return revisao


def revisoes_expiradas():
    """Queryset de revisões com prazo_em < agora e concluido_em IS NULL."""
    return Revisao.objects.filter(
        prazo_em__lt=timezone.now(),
        concluido_em__isnull=True,
    )
