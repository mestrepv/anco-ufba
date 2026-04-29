"""
Tasks assincronas (django-q2) do app acervo.

Em dev/teste, Q_CLUSTER tem `sync=True` e essas funcoes rodam no mesmo
processo. Em prod, sao despachadas para o worker.
"""

from __future__ import annotations

import logging

from django.core.mail import send_mail

from .aprovacao import avaliar_apos_revisao
from .models import Analise, Revisao
from .sorteio import (
    executar_sorteio,
    re_sortear_revisao_expirada,
    revisoes_expiradas,
)

logger = logging.getLogger(__name__)


def task_sortear_revisores(analise_id: int) -> dict:
    """Sorteia revisores para a analise. Returns dict serializavel para log."""
    try:
        analise = Analise.objects.get(pk=analise_id)
    except Analise.DoesNotExist:
        logger.error("task_sortear_revisores: analise %s nao existe", analise_id)
        return {"ok": False, "erro": "analise_nao_existe"}

    resultado = executar_sorteio(analise)
    if resultado.estruturais_criadas:
        _notificar_revisores(analise, resultado.estruturais_criadas, resultado.cegas_criadas)
    return {
        "ok": True,
        "estruturais": resultado.estruturais_criadas,
        "cegas": resultado.cegas_criadas,
        "fila_de_espera": resultado.fila_de_espera,
        "motivo": resultado.motivo,
    }


def task_avaliar_apos_revisao(analise_id: int) -> dict:
    """Reavalia a analise apos uma revisao concluir."""
    try:
        analise = Analise.objects.get(pk=analise_id)
    except Analise.DoesNotExist:
        logger.error("task_avaliar_apos_revisao: analise %s nao existe", analise_id)
        return {"ok": False, "erro": "analise_nao_existe"}

    resultado = avaliar_apos_revisao(analise)
    if resultado.decidida and resultado.novo_status == Analise.Status.PUBLICADA:
        _notificar_publicacao(analise)
    elif resultado.decidida and resultado.novo_status == Analise.Status.RASCUNHO:
        _notificar_volta_para_rascunho(analise, resultado.motivo)

    return {
        "ok": True,
        "decidida": resultado.decidida,
        "novo_status": resultado.novo_status,
        "motivo": resultado.motivo,
    }


def task_verificar_prazos() -> dict:
    """Cron diario: re-sorteia revisoes com prazo expirado."""
    re_sorteadas = 0
    sem_substituto = 0
    for r in revisoes_expiradas().select_related("analise", "revisor"):
        novo = re_sortear_revisao_expirada(r)
        if novo is None:
            sem_substituto += 1
        else:
            re_sorteadas += 1
    return {"ok": True, "re_sorteadas": re_sorteadas, "sem_substituto": sem_substituto}


# ----------------------------------------------------------------------
# Notificacoes (best-effort; falhas sao logadas mas nao quebram o fluxo)
# ----------------------------------------------------------------------


def _notificar_revisores(analise: Analise, estruturais: int, cegas: int) -> None:
    revisoes = Revisao.objects.filter(analise=analise).select_related("revisor")
    for r in revisoes:
        if not r.revisor.email:
            continue
        # Em revisoes cegas, NAO revelar nome do autor
        if r.tipo == Revisao.Tipo.CEGA:
            corpo = (
                f"Olá!\n\n"
                f"Você foi sorteado para uma revisão CEGA. A autoria está oculta.\n"
                f"Prazo: {r.prazo_em.strftime('%d/%m/%Y')}.\n\n"
                f"Acesse 'Minhas revisões' na plataforma."
            )
        else:
            corpo = (
                f"Olá!\n\n"
                f"Você foi sorteado para revisão estrutural da análise de {analise.analista}.\n"
                f"Artigo: {analise.artigo.titulo[:120]}\n"
                f"Prazo: {r.prazo_em.strftime('%d/%m/%Y')}.\n\n"
                f"Acesse 'Minhas revisões' na plataforma."
            )
        try:
            send_mail(
                "[AnCo] Você foi sorteado para uma revisão",
                corpo,
                from_email=None,
                recipient_list=[r.revisor.email],
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao enviar e-mail de revisao para %s", r.revisor)


def _notificar_publicacao(analise: Analise) -> None:
    if analise.analista.email:
        send_mail(
            "[AnCo] Sua análise foi publicada",
            (
                f"Olá!\n\n"
                f"Sua análise do artigo '{analise.artigo.titulo[:120]}' foi aprovada "
                f"por todos os revisores e está publicada no acervo."
            ),
            from_email=None,
            recipient_list=[analise.analista.email],
            fail_silently=True,
        )


def _notificar_volta_para_rascunho(analise: Analise, motivo: str) -> None:
    if analise.analista.email:
        send_mail(
            "[AnCo] Sua análise voltou para rascunho",
            (
                f"Olá!\n\n"
                f"Sua análise do artigo '{analise.artigo.titulo[:120]}' "
                f"recebeu pareceres da revisão por pares.\n\n"
                f"Motivo: {motivo}\n\n"
                f"Acesse a plataforma para ver os comentários e revisar."
            ),
            from_email=None,
            recipient_list=[analise.analista.email],
            fail_silently=True,
        )
