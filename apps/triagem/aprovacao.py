"""Avaliação das decisões de triagem (PRISMA-ScR), ciente das etapas.

Quando TODAS as decisões de um registro **na etapa atual** estão concluídas:
- todas `incluir`  -> avança (1ª etapa em 2 estágios: `incluido_ta`; senão `incluido`);
- todas `excluir`  -> excluído (`excluido` na 1ª etapa, `excluido_tc` na 2ª);
- divergência (mistura, ou qualquer `duvida`) -> permanece na etapa,
  sinalizado para **desempate** por curador/terceiro (não decide aqui).

A etapa de texto completo (2º estágio) só existe quando
`protocolo.usa_texto_completo` está ativo; do contrário o fluxo é idêntico ao
de etapa única (comportamento padrão preservado).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import DecisaoTriagem, RegistroTriagem

logger = logging.getLogger(__name__)

_St = RegistroTriagem.Status
_Dec = RegistroTriagem.Decisao
_Et = DecisaoTriagem.Etapa


@dataclass
class ResultadoAvaliacao:
    decidida: bool
    novo_status: str | None
    motivo: str = ""
    precisa_desempate: bool = False


def etapa_atual(registro: RegistroTriagem) -> str:
    """Etapa (TA/TC) cujas decisões estão abertas para este registro."""
    if registro.status == _St.EM_TEXTO:
        return _Et.TEXTO_COMPLETO
    return _Et.TITULO_RESUMO


def destino(registro: RegistroTriagem, decisao: str) -> str:
    """Status resultante de uma decisão consolidada, ciente da etapa atual.

    1ª etapa + protocolo de 2 estágios + INCLUIR -> `incluido_ta` (vai ao texto);
    caso contrário INCLUIR -> `incluido`. EXCLUIR -> `excluido`/`excluido_tc`.
    """
    em_texto = registro.status == _St.EM_TEXTO
    if decisao == _Dec.INCLUIR:
        if not em_texto and registro.protocolo.usa_texto_completo:
            return _St.INCLUIDO_TA
        return _St.INCLUIDO
    return _St.EXCLUIDO_TC if em_texto else _St.EXCLUIDO


@transaction.atomic
def consolidar_registro(
    registro: RegistroTriagem, decisao: str, *, motivo: str = "", por=None
) -> str:
    """Aplica a decisão consolidada (consenso ou desempate) e avança o status.

    Usada tanto pela avaliação automática quanto pelo desempate manual, para
    garantir uma única regra de transição. Retorna o novo status.
    """
    status = destino(registro, decisao)
    registro.status = status
    campos = ["status"]
    if status in RegistroTriagem.TERMINAIS:
        registro.decisao_final = decisao
        registro.decidida_em = timezone.now()
        campos += ["decisao_final", "decidida_em"]
    if motivo and status in (_St.EXCLUIDO, _St.EXCLUIDO_TC):
        registro.motivo_exclusao = motivo
        campos.append("motivo_exclusao")
    if por is not None:
        registro.decidida_por = por
        campos.append("decidida_por")
    registro.save(update_fields=campos)
    logger.info("Registro %s consolidado: %s (%s)", registro.pk, status, decisao)
    return status


def _todas_concluidas(registro: RegistroTriagem, etapa: str) -> bool:
    return not DecisaoTriagem.objects.filter(
        registro=registro, etapa=etapa, concluido_em__isnull=True
    ).exists()


def _decisoes(registro: RegistroTriagem, etapa: str) -> list[str]:
    return list(
        DecisaoTriagem.objects.filter(
            registro=registro, etapa=etapa, decisao__isnull=False
        ).values_list("decisao", flat=True)
    )


def _motivos(registro: RegistroTriagem, etapa: str) -> str:
    motivos = (
        DecisaoTriagem.objects.filter(registro=registro, etapa=etapa)
        .exclude(motivo_exclusao="")
        .values_list("motivo_exclusao", flat=True)
    )
    return " | ".join(m.strip() for m in motivos if m.strip())


@transaction.atomic
def avaliar_apos_triagem(registro: RegistroTriagem) -> ResultadoAvaliacao:
    """Decide o destino do registro quando todas as decisões da etapa concluem."""
    registro.refresh_from_db()

    if registro.status not in (_St.EM_TRIAGEM, _St.EM_TEXTO):
        return ResultadoAvaliacao(False, None, f"Status={registro.status}.")

    etapa = etapa_atual(registro)
    if not _todas_concluidas(registro, etapa):
        return ResultadoAvaliacao(False, None, "Faltam decisões.")

    decisoes = _decisoes(registro, etapa)

    if decisoes and all(d == _Dec.INCLUIR for d in decisoes):
        novo = consolidar_registro(registro, _Dec.INCLUIR)
        return ResultadoAvaliacao(True, novo, "Consenso: incluir.")
    if decisoes and all(d == _Dec.EXCLUIR for d in decisoes):
        novo = consolidar_registro(registro, _Dec.EXCLUIR, motivo=_motivos(registro, etapa))
        return ResultadoAvaliacao(True, novo, "Consenso: excluir.")

    # Divergência ou dúvida → aguarda desempate (não muda o status).
    logger.info("Registro %s divergente — aguarda desempate: %s", registro.pk, decisoes)
    return ResultadoAvaliacao(
        False,
        None,
        "Divergência entre revisores — aguarda desempate.",
        precisa_desempate=True,
    )


def registros_para_desempate(protocolo):
    """Registros em triagem (qualquer etapa), com decisões concluídas e divergentes."""
    candidatos = RegistroTriagem.objects.filter(
        protocolo=protocolo, status__in=[_St.EM_TRIAGEM, _St.EM_TEXTO]
    ).prefetch_related("decisoes")
    pendentes = []
    for r in candidatos:
        etapa = etapa_atual(r)
        decisoes = [d for d in r.decisoes.all() if d.etapa == etapa]
        if not decisoes or any(d.concluido_em is None for d in decisoes):
            continue
        valores = {d.decisao for d in decisoes}
        if valores != {_Dec.INCLUIR} and valores != {_Dec.EXCLUIR}:
            pendentes.append(r)
    return pendentes
