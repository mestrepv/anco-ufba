"""Sorteio de revisores independentes para a triagem (PRISMA-ScR).

Espelha `apps/acervo/sorteio.py` (revisão cega de resenha), operando sobre
`RegistroTriagem`/`DecisaoTriagem`. Regras:

- Sorteia `protocolo.n_revisores` revisores (≥2), prazo `protocolo.prazo_dias`.
- Exclui quem coletou o registro (`Busca.criado_por` das origens) — independência.
- Exclui quem já decidiu sobre o registro (re-sorteios).
- Respeita `aceita_revisoes`, `revisor_aprovado` e `limite_revisoes_simultaneas`
  (conta triagens pendentes).
- Não sorteia registros `ja_no_acervo` (já catalogados, inclusive legado).
- Revisores insuficientes → fila de espera (mantém `identificado`).
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

from .models import DecisaoTriagem, RegistroTriagem

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class ResultadoSorteio:
    criadas: int
    fila_de_espera: bool
    motivo: str = ""


def _coletores(registro: RegistroTriagem) -> set[int]:
    """IDs de quem rodou as buscas de origem do registro (conflito de interesse)."""
    return set(
        registro.origem_buscas.exclude(criado_por__isnull=True).values_list(
            "criado_por_id", flat=True
        )
    )


def revisores_elegiveis(registro: RegistroTriagem, excluir_ids: set[int] | None = None):
    """Queryset de Users elegíveis a triar `registro`."""
    excluir = set(excluir_ids or set()) | _coletores(registro)
    return (
        User.objects.filter(
            papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
            is_active=True,
            aceita_revisoes=True,
            revisor_aprovado=True,
        )
        .exclude(pk__in=excluir)
        .annotate(
            triagens_pendentes=Count(
                "triagens_feitas",
                filter=Q(triagens_feitas__concluido_em__isnull=True),
            )
        )
        .filter(triagens_pendentes__lt=F("limite_revisoes_simultaneas"))
    )


def _sortear_n(elegiveis_qs, n: int) -> list:
    candidatos = list(elegiveis_qs)
    if not candidatos:
        return []
    random.shuffle(candidatos)
    return candidatos[:n]


@transaction.atomic
def executar_sorteio(registro: RegistroTriagem) -> ResultadoSorteio:
    """Sorteia revisores para um registro `identificado` (idempotente)."""
    if registro.ja_no_acervo:
        return ResultadoSorteio(0, False, "Já no acervo — não entra em triagem.")
    if registro.status not in RegistroTriagem.EM_ABERTO:
        return ResultadoSorteio(0, False, f"Status {registro.status} não tria.")

    pendentes = DecisaoTriagem.objects.filter(
        registro=registro, concluido_em__isnull=True
    )
    if pendentes.exists():
        return ResultadoSorteio(0, False, "Já há ciclo de triagem pendente.")

    ja_decidiram = set(
        DecisaoTriagem.objects.filter(registro=registro).values_list(
            "revisor_id", flat=True
        )
    )
    n = registro.protocolo.n_revisores
    elegiveis = revisores_elegiveis(registro, excluir_ids=ja_decidiram)
    sorteados = _sortear_n(elegiveis, n)

    if len(sorteados) < n:
        logger.warning(
            "Faltam revisores para registro %s (%d de %d)", registro.pk, len(sorteados), n
        )
        return ResultadoSorteio(
            0, True, f"Revisores insuficientes ({len(sorteados)} de {n})."
        )

    agora = timezone.now()
    prazo = agora + timedelta(days=registro.protocolo.prazo_dias)
    for revisor in sorteados:
        DecisaoTriagem.objects.create(registro=registro, revisor=revisor, prazo_em=prazo)

    registro.status = RegistroTriagem.Status.EM_TRIAGEM
    registro.save(update_fields=["status"])
    return ResultadoSorteio(criadas=len(sorteados), fila_de_espera=False)


@transaction.atomic
def re_sortear_triagem_expirada(decisao: DecisaoTriagem) -> DecisaoTriagem | None:
    """Substitui um revisor expirado por outro elegível no mesmo registro."""
    if decisao.concluido_em is not None:
        return decisao

    registro = decisao.registro
    ja_designados = set(
        DecisaoTriagem.objects.filter(registro=registro).values_list(
            "revisor_id", flat=True
        )
    )
    novos = _sortear_n(revisores_elegiveis(registro, excluir_ids=ja_designados), 1)
    if not novos:
        logger.warning("Sem substituto para decisão de triagem %s", decisao.pk)
        return None

    decisao.revisor = novos[0]
    decisao.prazo_em = timezone.now() + timedelta(days=registro.protocolo.prazo_dias)
    decisao.save(update_fields=["revisor", "prazo_em"])
    return decisao


def triagens_expiradas():
    return DecisaoTriagem.objects.filter(
        prazo_em__lt=timezone.now(), concluido_em__isnull=True
    )
