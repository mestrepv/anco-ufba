"""
Servico de avaliacao de pareceres e transicao de status apos revisoes.

Spec secao 5.5:
- Sem resenha: 2 estruturais com `aprovar` -> `aprovada` -> `publicada`.
- Com resenha: 2 estruturais + 2 cegas, todas `aprovar` -> `aprovada` -> `publicada`.
- Algum parecer `ajustes`: volta para `rascunho` (com comentarios).
- Algum parecer `rejeitar`: volta para `rascunho` (idem).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import Analise, Revisao

logger = logging.getLogger(__name__)


@dataclass
class ResultadoAvaliacao:
    decidida: bool  # True se ja eh possivel decidir; False se ainda faltam pareceres
    novo_status: str | None  # status para qual transitou (ou None se nao transitou)
    motivo: str = ""


def _todas_concluidas(analise: Analise) -> bool:
    return not Revisao.objects.filter(analise=analise, concluido_em__isnull=True).exists()


def _pareceres(analise: Analise) -> list[str]:
    return list(
        Revisao.objects.filter(analise=analise, parecer__isnull=False).values_list(
            "parecer", flat=True
        )
    )


@transaction.atomic
def avaliar_apos_revisao(analise: Analise) -> ResultadoAvaliacao:
    """
    Decide o destino da analise apos uma revisao ser concluida.

    Soh transita quando TODAS as revisoes pendentes estao concluidas.
    """
    # Releitura para evitar race com cache de instancia
    analise.refresh_from_db()

    if analise.status != Analise.Status.EM_REVISAO:
        return ResultadoAvaliacao(
            decidida=False,
            novo_status=None,
            motivo=f"Analise nao esta em revisao (status={analise.status}).",
        )

    if not _todas_concluidas(analise):
        return ResultadoAvaliacao(
            decidida=False,
            novo_status=None,
            motivo="Faltam pareceres.",
        )

    pareceres = _pareceres(analise)
    if any(p == Revisao.Parecer.REJEITAR for p in pareceres):
        return _voltar_para_rascunho(analise, motivo="Pelo menos um parecer rejeitou.")

    if any(p == Revisao.Parecer.AJUSTES for p in pareceres):
        return _voltar_para_rascunho(analise, motivo="Pelo menos um parecer pediu ajustes.")

    if all(p == Revisao.Parecer.APROVAR for p in pareceres):
        return _publicar(analise)

    # caso defensivo: pareceres com valor inesperado
    logger.error(
        "Analise %s tem pareceres inesperados: %s",
        analise.pk,
        pareceres,
    )
    return ResultadoAvaliacao(
        decidida=False,
        novo_status=None,
        motivo=f"Pareceres inesperados: {pareceres}",
    )


def _voltar_para_rascunho(analise: Analise, motivo: str) -> ResultadoAvaliacao:
    analise.status = Analise.Status.RASCUNHO
    analise.save(update_fields=["status"])
    logger.info("Analise %s voltou a rascunho: %s", analise.pk, motivo)
    return ResultadoAvaliacao(
        decidida=True,
        novo_status=Analise.Status.RASCUNHO,
        motivo=motivo,
    )


def _publicar(analise: Analise) -> ResultadoAvaliacao:
    """Transicao em duas etapas: em_revisao -> aprovada -> publicada."""
    agora = timezone.now()
    analise.status = Analise.Status.PUBLICADA
    analise.publicada_em = agora
    analise.save(update_fields=["status", "publicada_em"])
    logger.info("Analise %s publicada em %s", analise.pk, agora)
    return ResultadoAvaliacao(
        decidida=True,
        novo_status=Analise.Status.PUBLICADA,
        motivo="Todos os pareceres aprovaram.",
    )
