"""Avaliação das decisões de triagem (PRISMA-ScR).

Quando TODAS as decisões de um registro estão concluídas:
- todas `incluir`  -> registro `incluido`  (decisao_final = incluir);
- todas `excluir`  -> registro `excluido`  (decisao_final = excluir);
- divergência (mistura, ou qualquer `duvida`) -> permanece `em_triagem`,
  sinalizado para **desempate** por curador/terceiro (não decide aqui).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import DecisaoTriagem, RegistroTriagem

logger = logging.getLogger(__name__)


@dataclass
class ResultadoAvaliacao:
    decidida: bool
    novo_status: str | None
    motivo: str = ""
    precisa_desempate: bool = False


def _todas_concluidas(registro: RegistroTriagem) -> bool:
    return not DecisaoTriagem.objects.filter(
        registro=registro, concluido_em__isnull=True
    ).exists()


def _decisoes(registro: RegistroTriagem) -> list[str]:
    return list(
        DecisaoTriagem.objects.filter(
            registro=registro, decisao__isnull=False
        ).values_list("decisao", flat=True)
    )


def _motivos(registro: RegistroTriagem) -> str:
    motivos = (
        DecisaoTriagem.objects.filter(registro=registro)
        .exclude(motivo_exclusao="")
        .values_list("motivo_exclusao", flat=True)
    )
    return " | ".join(m.strip() for m in motivos if m.strip())


@transaction.atomic
def avaliar_apos_triagem(registro: RegistroTriagem) -> ResultadoAvaliacao:
    """Decide o destino do registro quando todas as decisões concluem."""
    registro.refresh_from_db()

    if registro.status != RegistroTriagem.Status.EM_TRIAGEM:
        return ResultadoAvaliacao(False, None, f"Status={registro.status}.")

    if not _todas_concluidas(registro):
        return ResultadoAvaliacao(False, None, "Faltam decisões.")

    decisoes = _decisoes(registro)
    I = RegistroTriagem.Decisao  # noqa: E741

    if decisoes and all(d == I.INCLUIR for d in decisoes):
        return _consolidar(registro, RegistroTriagem.Status.INCLUIDO, I.INCLUIR)
    if decisoes and all(d == I.EXCLUIR for d in decisoes):
        return _consolidar(
            registro, RegistroTriagem.Status.EXCLUIDO, I.EXCLUIR, _motivos(registro)
        )

    # Divergência ou dúvida → aguarda desempate (não muda o status).
    logger.info("Registro %s divergente — aguarda desempate: %s", registro.pk, decisoes)
    return ResultadoAvaliacao(
        False, None, "Divergência entre revisores — aguarda desempate.",
        precisa_desempate=True,
    )


def _consolidar(
    registro: RegistroTriagem, status: str, decisao_final: str, motivo: str = ""
) -> ResultadoAvaliacao:
    registro.status = status
    registro.decisao_final = decisao_final
    registro.decidida_em = timezone.now()
    if motivo:
        registro.motivo_exclusao = motivo
    registro.save(
        update_fields=["status", "decisao_final", "decidida_em", "motivo_exclusao"]
    )
    logger.info("Registro %s consolidado: %s", registro.pk, status)
    return ResultadoAvaliacao(True, status, f"Consenso: {decisao_final}.")


def registros_para_desempate(protocolo):
    """Registros em triagem, com todas as decisões concluídas e divergentes."""
    candidatos = (
        RegistroTriagem.objects.filter(
            protocolo=protocolo, status=RegistroTriagem.Status.EM_TRIAGEM
        )
        .prefetch_related("decisoes")
    )
    pendentes = []
    for r in candidatos:
        decisoes = list(r.decisoes.all())
        if not decisoes or any(d.concluido_em is None for d in decisoes):
            continue
        valores = {d.decisao for d in decisoes}
        if valores != {RegistroTriagem.Decisao.INCLUIR} and valores != {
            RegistroTriagem.Decisao.EXCLUIR
        }:
            pendentes.append(r)
    return pendentes
