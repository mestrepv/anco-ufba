"""Calibração (piloto) da triagem — Fase 11.5.

Antes do run real, toda a equipe tria uma **amostra comum** e medimos a
confiabilidade entre avaliadores (κ de Fleiss). Se a concordância for baixa, os
critérios são refinados (nova versão do protocolo) antes de triar tudo.

Isolamento: as decisões usam a etapa `CALIBRACAO`; o status dos registros não
muda (continuam `identificado` e entram no run real normalmente), e o κ oficial
da triagem (etapa título/resumo) não é afetado.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .concordancia import _interpretar, fleiss_e_acordo
from .models import DecisaoTriagem, RegistroTriagem, RodadaCalibracao

logger = logging.getLogger(__name__)
User = get_user_model()

_Et = DecisaoTriagem.Etapa


def revisores_da_equipe(protocolo):
    """Revisores aprovados que são **membros do projeto** (Fase 12.2)."""
    return User.objects.filter(
        papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
        is_active=True,
        aceita_revisoes=True,
        revisor_aprovado=True,
        projetos_triagem__projeto=protocolo,
    )


@transaction.atomic
def iniciar_calibracao(protocolo, tamanho: int, criada_por=None) -> RodadaCalibracao | None:
    """Sorteia uma amostra de `tamanho` registros e designa TODA a equipe a triá-los.

    Retorna a `RodadaCalibracao` criada, ou `None` se não houver amostra/equipe.
    """
    elegiveis = list(
        protocolo.registros.filter(
            status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
        ).values_list("pk", flat=True)
    )
    equipe = list(revisores_da_equipe(protocolo))
    if not elegiveis or len(equipe) < 2:
        return None

    amostra_ids = random.sample(elegiveis, min(tamanho, len(elegiveis)))
    rodada = RodadaCalibracao.objects.create(
        protocolo=protocolo, criada_por=criada_por, n_revisores=len(equipe)
    )
    rodada.registros.set(amostra_ids)

    prazo = timezone.now() + timedelta(days=protocolo.prazo_dias)
    for rid in amostra_ids:
        for revisor in equipe:
            DecisaoTriagem.objects.get_or_create(
                registro_id=rid,
                revisor=revisor,
                etapa=_Et.CALIBRACAO,
                defaults={"prazo_em": prazo},
            )
    logger.info("Calibração %s: %d itens × %d revisores", rodada.pk, len(amostra_ids), len(equipe))
    return rodada


@dataclass
class ResultadoCalibracao:
    n_itens: int = 0
    n_revisores: int = 0
    completos: int = 0  # itens com todas as decisões concluídas
    perc_acordo: float | None = None
    kappa: float | None = None
    interpretacao: str = "—"
    pronto: bool = False  # κ ≥ 0,6 (substancial) → equipe calibrada
    distribuicao: list = field(default_factory=list)

    @property
    def perc_pct(self) -> int | None:
        return round(self.perc_acordo * 100) if self.perc_acordo is not None else None


def calcular(rodada: RodadaCalibracao) -> ResultadoCalibracao:
    """κ de Fleiss sobre os itens totalmente triados da rodada."""
    decisoes = DecisaoTriagem.objects.filter(
        registro__in=rodada.registros.all(), etapa=_Et.CALIBRACAO
    ).values_list("registro_id", "decisao", "concluido_em")

    por_registro: dict[int, list] = {}
    for rid, dec, concluido in decisoes:
        por_registro.setdefault(rid, []).append((dec, concluido))

    n = rodada.n_revisores
    itens = [
        [dec for dec, _c in v]
        for v in por_registro.values()
        if len(v) == n and all(c is not None for _d, c in v)
    ]
    if not itens:
        return ResultadoCalibracao(n_itens=rodada.registros.count(), n_revisores=n)

    perc, kappa, distribuicao = fleiss_e_acordo(itens, n)
    rotulos = dict(DecisaoTriagem._meta.get_field("decisao").choices or [])
    return ResultadoCalibracao(
        n_itens=rodada.registros.count(),
        n_revisores=n,
        completos=len(itens),
        perc_acordo=perc,
        kappa=kappa,
        interpretacao=_interpretar(kappa),
        pronto=kappa is not None and kappa >= 0.6,
        distribuicao=[(rotulos.get(c, c), total) for c, total in distribuicao],
    )


@transaction.atomic
def fechar_calibracao(rodada: RodadaCalibracao) -> ResultadoCalibracao:
    """Congela o resultado da rodada (κ/acordo) e marca `fechada_em`."""
    res = calcular(rodada)
    rodada.n_itens = res.completos
    rodada.perc_acordo = res.perc_acordo
    rodada.kappa = res.kappa
    rodada.fechada_em = timezone.now()
    rodada.save(update_fields=["n_itens", "perc_acordo", "kappa", "fechada_em"])
    return res
