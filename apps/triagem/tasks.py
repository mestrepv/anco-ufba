"""Tasks assíncronas (django-q2) da triagem.

Em dev/teste, `Q_CLUSTER.sync=True` roda no mesmo processo; em prod, no worker.
"""

from __future__ import annotations

import logging

from django.core.mail import send_mail

from .aprovacao import avaliar_apos_triagem
from .models import DecisaoTriagem, ProtocoloTriagem, RegistroTriagem
from .sorteio import (
    executar_sorteio,
    re_sortear_triagem_expirada,
    triagens_expiradas,
)

logger = logging.getLogger(__name__)


def task_sortear_triagem(registro_id: int) -> dict:
    """Sorteia revisores para um registro identificado."""
    try:
        registro = RegistroTriagem.objects.select_related("protocolo").get(pk=registro_id)
    except RegistroTriagem.DoesNotExist:
        logger.error("task_sortear_triagem: registro %s não existe", registro_id)
        return {"ok": False, "erro": "registro_nao_existe"}

    resultado = executar_sorteio(registro)
    if resultado.criadas:
        _notificar_revisores_triagem(registro)
    return {
        "ok": True,
        "criadas": resultado.criadas,
        "fila_de_espera": resultado.fila_de_espera,
        "motivo": resultado.motivo,
    }


def task_avaliar_apos_triagem(registro_id: int) -> dict:
    """Reavalia o registro após uma decisão de triagem concluir."""
    try:
        registro = RegistroTriagem.objects.select_related("protocolo").get(pk=registro_id)
    except RegistroTriagem.DoesNotExist:
        logger.error("task_avaliar_apos_triagem: registro %s não existe", registro_id)
        return {"ok": False, "erro": "registro_nao_existe"}

    resultado = avaliar_apos_triagem(registro)
    # A promoção dos incluídos ao acervo entra na Fase 9.5.
    return {
        "ok": True,
        "decidida": resultado.decidida,
        "novo_status": resultado.novo_status,
        "precisa_desempate": resultado.precisa_desempate,
        "motivo": resultado.motivo,
    }


def task_verificar_prazos_triagem() -> dict:
    """Cron: re-sorteia decisões de triagem com prazo expirado."""
    re_sorteadas = 0
    sem_substituto = 0
    for d in triagens_expiradas().select_related("registro__protocolo", "revisor"):
        novo = re_sortear_triagem_expirada(d)
        if novo is None:
            sem_substituto += 1
        else:
            re_sorteadas += 1
    return {"ok": True, "re_sorteadas": re_sorteadas, "sem_substituto": sem_substituto}


def iniciar_triagem(protocolo: ProtocoloTriagem, registro_ids: list[int] | None = None) -> int:
    """Enfileira sorteio para registros `identificado` não-`ja_no_acervo`.

    Retorna quantos registros foram enfileirados. Usado pela ação de UI (9.4).
    """
    from django_q.tasks import async_task

    qs = protocolo.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    )
    if registro_ids is not None:
        qs = qs.filter(pk__in=registro_ids)
    ids = list(qs.values_list("pk", flat=True))
    for rid in ids:
        async_task("apps.triagem.tasks.task_sortear_triagem", rid)
    return len(ids)


# --------------------------------------------------------------------------- #
# Notificações (best-effort; falham silenciosamente)
# --------------------------------------------------------------------------- #

def _enviar(assunto: str, corpo: str, destinatarios: list[str]) -> None:
    destinatarios = [e for e in destinatarios if e]
    if not destinatarios:
        return
    try:
        send_mail(assunto, corpo, None, destinatarios, fail_silently=True)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao enviar notificação de triagem")


def _notificar_revisores_triagem(registro: RegistroTriagem) -> None:
    pendentes = DecisaoTriagem.objects.filter(
        registro=registro, concluido_em__isnull=True
    ).select_related("revisor")
    for d in pendentes:
        _enviar(
            "Triagem AnCo — você foi sorteado",
            (
                "Você foi sorteado para triar um registro (inclusão/exclusão por "
                f"título e resumo). Prazo: {d.prazo_em:%d/%m/%Y}.\n\n"
                "Acesse 'Minhas triagens' na plataforma."
            ),
            [d.revisor.email],
        )
