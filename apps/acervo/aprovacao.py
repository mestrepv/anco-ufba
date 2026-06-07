"""
Avaliação dos pareceres da revisão cega de uma Resenha.

A revisão por pares vale só para resenhas. Quando todas as revisões cegas de
uma resenha estão concluídas:
- algum parecer `rejeitar` ou `ajustes`  -> resenha volta a `rascunho`;
- todos `aprovar`                         -> resenha vai a `revisada`
  (aguardando confirmação de um curador para então ser publicada).

A publicação da resenha (revisada -> publicada) é ação explícita do curador,
fora deste módulo. A publicação da análise é independente (aprovação de curador).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

from .models import Resenha, Revisao

logger = logging.getLogger(__name__)


@dataclass
class ResultadoAvaliacao:
    decidida: bool  # True se já é possível decidir; False se faltam pareceres
    novo_status: str | None  # status para o qual transitou (ou None)
    motivo: str = ""


def _todas_concluidas(resenha: Resenha) -> bool:
    return not Revisao.objects.filter(resenha=resenha, concluido_em__isnull=True).exists()


def _pareceres(resenha: Resenha) -> list[str]:
    return list(
        Revisao.objects.filter(resenha=resenha, parecer__isnull=False).values_list(
            "parecer", flat=True
        )
    )


@transaction.atomic
def avaliar_apos_revisao_cega(resenha: Resenha) -> ResultadoAvaliacao:
    """
    Decide o destino da resenha após uma revisão cega ser concluída.

    Só transita quando TODAS as revisões pendentes estão concluídas.
    """
    resenha.refresh_from_db()

    if resenha.status != Resenha.Status.EM_REVISAO:
        return ResultadoAvaliacao(
            decidida=False,
            novo_status=None,
            motivo=f"Resenha não está em revisão (status={resenha.status}).",
        )

    if not _todas_concluidas(resenha):
        return ResultadoAvaliacao(False, None, "Faltam pareceres.")

    pareceres = _pareceres(resenha)
    if any(p == Revisao.Parecer.REJEITAR for p in pareceres):
        return _voltar_para_rascunho(resenha, "Pelo menos um parecer rejeitou.")

    if any(p == Revisao.Parecer.AJUSTES for p in pareceres):
        return _voltar_para_rascunho(resenha, "Pelo menos um parecer pediu ajustes.")

    if pareceres and all(p == Revisao.Parecer.APROVAR for p in pareceres):
        return _marcar_revisada(resenha)

    logger.error("Resenha %s com pareceres inesperados: %s", resenha.pk, pareceres)
    return ResultadoAvaliacao(False, None, f"Pareceres inesperados: {pareceres}")


def _voltar_para_rascunho(resenha: Resenha, motivo: str) -> ResultadoAvaliacao:
    resenha.status = Resenha.Status.RASCUNHO
    resenha.save(update_fields=["status"])
    logger.info("Resenha %s voltou a rascunho: %s", resenha.pk, motivo)
    return ResultadoAvaliacao(True, Resenha.Status.RASCUNHO, motivo)


def _marcar_revisada(resenha: Resenha) -> ResultadoAvaliacao:
    """Cegas aprovaram: resenha fica `revisada`, aguardando curador confirmar."""
    resenha.status = Resenha.Status.REVISADA
    resenha.save(update_fields=["status"])
    logger.info("Resenha %s revisada — aguardando curadoria", resenha.pk)
    return ResultadoAvaliacao(
        True,
        Resenha.Status.REVISADA,
        "Todos os pareceres aprovaram — aguardando confirmação da curadoria.",
    )
