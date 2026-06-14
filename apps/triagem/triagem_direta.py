"""Triagem direta: atribuição determinística de revisores, sem sorteio.

Alternativa ao `sorteio.py` para revisões **sem distribuição aleatória**: o
curador escolhe explicitamente os revisores e **todos triam todos** os registros
identificados. Reaproveita `DecisaoTriagem` — consenso/desempate/promoção
(`aprovacao.py`, `signals.py`) já reagem às decisões, independentemente de como
foram criadas.

Diferenças face ao sorteio (intencionais):
- não aplica aleatoriedade nem a exclusão por independência (`_coletores`);
- não exige `revisor_aprovado`/`aceita_revisoes` (o curador designa quem tria);
- exige que cada revisor seja **membro do projeto** (mesma garantia do sorteio).

Idempotente: rodar de novo só cria as decisões que faltam (a UniqueConstraint
`(registro, revisor, etapa)` é a rede de segurança no banco).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import DecisaoTriagem, ProjetoMembro, ProtocoloTriagem, RegistroTriagem

logger = logging.getLogger(__name__)


@dataclass
class ResultadoAtribuicao:
    registros: int  # registros que (re)entraram em triagem
    decisoes: int  # decisões criadas nesta passagem
    revisores: int  # revisores designados
    motivo: str = ""


def revisores_validos(protocolo: ProtocoloTriagem, ids) -> list:
    """Membros do projeto entre os `ids` informados (preserva a ordem dos ids)."""
    membros = {
        m.usuario_id: m.usuario
        for m in ProjetoMembro.objects.filter(
            projeto=protocolo, usuario_id__in=list(ids)
        ).select_related("usuario")
    }
    return [membros[i] for i in dict.fromkeys(ids) if i in membros]


@transaction.atomic
def atribuir_triagem_direta(
    protocolo: ProtocoloTriagem,
    revisores: list,
    etapa: str = DecisaoTriagem.Etapa.TITULO_RESUMO,
) -> ResultadoAtribuicao:
    """Cria decisões de triagem para `revisores` em cada registro identificado.

    Cada registro `identificado` (não `ja_no_acervo`) recebe uma `DecisaoTriagem`
    por revisor e passa a `em_triagem`. Registros que já têm alguma decisão na
    etapa só ganham os revisores que faltam (idempotência / adicionar revisor
    depois). Não toca registros já decididos ou em outra etapa.
    """
    revisores = list(revisores)
    if not revisores:
        return ResultadoAtribuicao(0, 0, 0, "Nenhum revisor designado.")

    prazo = timezone.now() + timedelta(days=protocolo.prazo_dias)
    qs = protocolo.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    )

    n_reg = n_dec = 0
    for registro in qs:
        ja = set(
            DecisaoTriagem.objects.filter(registro=registro, etapa=etapa).values_list(
                "revisor_id", flat=True
            )
        )
        criou = False
        for revisor in revisores:
            if revisor.id in ja:
                continue
            DecisaoTriagem.objects.create(
                registro=registro, revisor=revisor, etapa=etapa, prazo_em=prazo
            )
            n_dec += 1
            criou = True
        if criou:
            registro.status = RegistroTriagem.Status.EM_TRIAGEM
            registro.save(update_fields=["status"])
            n_reg += 1

    logger.info(
        "Triagem direta no projeto %s: %d registros, %d decisões, %d revisores",
        protocolo.slug,
        n_reg,
        n_dec,
        len(revisores),
    )
    return ResultadoAtribuicao(n_reg, n_dec, len(revisores))
