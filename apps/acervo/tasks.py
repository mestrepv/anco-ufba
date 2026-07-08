"""
Tasks assíncronas (django-q2) do app acervo.

Revisão por pares vale só para resenhas. Em dev/teste, Q_CLUSTER tem
`sync=True` e estas funções rodam no mesmo processo. Em prod, no worker.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .aprovacao import avaliar_apos_revisao_cega
from .models import Analise, Artigo, Resenha, Revisao
from .services import aplicar_resultado_no_artigo, validar_link
from .sorteio import (
    executar_sorteio,
    re_sortear_revisao_expirada,
    revisoes_expiradas,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def task_sortear_revisores_cegos(resenha_id: int) -> dict:
    """Sorteia revisores cegos para a resenha. Returns dict serializável."""
    try:
        resenha = Resenha.objects.select_related("analise__artigo").get(pk=resenha_id)
    except Resenha.DoesNotExist:
        logger.error("task_sortear_revisores_cegos: resenha %s não existe", resenha_id)
        return {"ok": False, "erro": "resenha_nao_existe"}

    resultado = executar_sorteio(resenha)
    if resultado.cegas_criadas:
        _notificar_revisores_cegos(resenha)
    return {
        "ok": True,
        "cegas": resultado.cegas_criadas,
        "fila_de_espera": resultado.fila_de_espera,
        "motivo": resultado.motivo,
    }


def task_avaliar_apos_revisao_cega(resenha_id: int) -> dict:
    """Reavalia a resenha após uma revisão cega concluir."""
    try:
        resenha = Resenha.objects.select_related("analise__artigo").get(pk=resenha_id)
    except Resenha.DoesNotExist:
        logger.error("task_avaliar_apos_revisao_cega: resenha %s não existe", resenha_id)
        return {"ok": False, "erro": "resenha_nao_existe"}

    resultado = avaliar_apos_revisao_cega(resenha)
    if resultado.decidida and resultado.novo_status == Resenha.Status.REVISADA:
        _notificar_curadores_resenha_revisada(resenha)
    elif resultado.decidida and resultado.novo_status == Resenha.Status.RASCUNHO:
        _notificar_resenha_volta_rascunho(resenha, resultado.motivo)

    return {
        "ok": True,
        "decidida": resultado.decidida,
        "novo_status": resultado.novo_status,
        "motivo": resultado.motivo,
    }


def task_verificar_prazos() -> dict:
    """Cron diário: re-sorteia revisões com prazo expirado."""
    re_sorteadas = 0
    sem_substituto = 0
    for r in revisoes_expiradas().select_related("resenha__analise", "revisor"):
        novo = re_sortear_revisao_expirada(r)
        if novo is None:
            sem_substituto += 1
        else:
            re_sorteadas += 1
    return {"ok": True, "re_sorteadas": re_sorteadas, "sem_substituto": sem_substituto}


def task_verificar_links(limite: int = 0) -> dict:
    """
    Cron semanal: faz HEAD em todos os link_acesso de Artigos cujas
    análises estão publicadas/legado. Atualiza link_status e
    link_ultima_verificacao. `limite` (0=todos) restringe para teste.
    """
    qs = (
        Artigo.objects.filter(
            analises__status__in=(Analise.Status.PUBLICADA, Analise.Status.LEGADO),
        )
        .exclude(link_acesso="")
        .distinct()
    )
    if limite:
        qs = qs[:limite]

    contagem = {"ok": 0, "quebrado": 0, "redireciona": 0, "pulados": 0, "total": 0}
    for artigo in qs.iterator(chunk_size=200):
        contagem["total"] += 1
        try:
            resultado = validar_link(artigo.link_acesso)
            aplicar_resultado_no_artigo(artigo, resultado)
            contagem[resultado.status] = contagem.get(resultado.status, 0) + 1
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao verificar link de Artigo %s", artigo.pk)
            contagem["pulados"] += 1
    return {"ok": True, **contagem}


# ----------------------------------------------------------------------
# Notificações (best-effort; falhas são logadas mas não quebram o fluxo)
# ----------------------------------------------------------------------


def _emails_curadores() -> list[str]:
    return list(
        User.objects.filter(papel=User.Papel.CURADOR, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _enviar(assunto: str, corpo: str, destinatarios: list[str]) -> None:
    destinatarios = [e for e in destinatarios if e]
    if not destinatarios:
        return
    try:
        send_mail(assunto, corpo, from_email=None, recipient_list=destinatarios, fail_silently=True)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao enviar e-mail: %s", assunto)


def _notificar_revisores_cegos(resenha: Resenha) -> None:
    """E-mail aos revisores cegos sorteados (autoria sempre oculta)."""
    for r in Revisao.objects.filter(resenha=resenha, concluido_em__isnull=True).select_related(
        "revisor"
    ):
        corpo = (
            "Olá!\n\n"
            "Você foi sorteado para uma revisão CEGA de uma resenha crítica. "
            "A autoria está oculta.\n"
            f"Prazo: {timezone.localtime(r.prazo_em).strftime('%d/%m/%Y')}.\n\n"
            "Acesse 'Minhas revisões' na plataforma."
        )
        _enviar("[AnCo] Você foi sorteado para uma revisão cega", corpo, [r.revisor.email])


def _notificar_curadores_resenha_revisada(resenha: Resenha) -> None:
    corpo = (
        "Olá!\n\n"
        "Uma resenha crítica passou pela revisão cega e está pronta para "
        "confirmação da curadoria.\n"
        f"Artigo: {resenha.analise.artigo.titulo[:120]}\n\n"
        "Acesse a fila de curadoria na plataforma."
    )
    _enviar("[AnCo] Resenha revisada — aguardando confirmação", corpo, _emails_curadores())


def _notificar_resenha_volta_rascunho(resenha: Resenha, motivo: str) -> None:
    autor = resenha.analise.analista
    corpo = (
        "Olá!\n\n"
        "A revisão cega da sua resenha crítica do artigo "
        f"'{resenha.analise.artigo.titulo[:120]}' devolveu pareceres.\n\n"
        f"Motivo: {motivo}\n\n"
        "Acesse a plataforma para ver os comentários e revisar."
    )
    _enviar("[AnCo] Sua resenha voltou para rascunho", corpo, [autor.email])


def notificar_analise_submetida(analise: Analise) -> None:
    """Avisa curadores de que há uma análise na fila de curadoria."""
    corpo = (
        "Olá!\n\n"
        "Uma análise foi submetida e aguarda aprovação da curadoria.\n"
        f"Artigo: {analise.artigo.titulo[:120]}\n\n"
        "Acesse a fila de curadoria na plataforma."
    )
    _enviar("[AnCo] Análise submetida para curadoria", corpo, _emails_curadores())


def notificar_publicacao_analise(analise: Analise) -> None:
    corpo = (
        "Olá!\n\n"
        f"Sua análise do artigo '{analise.artigo.titulo[:120]}' foi aprovada "
        "pela curadoria e está publicada no acervo."
    )
    _enviar("[AnCo] Sua análise foi publicada", corpo, [analise.analista.email])


def notificar_analise_devolvida(analise: Analise, motivo: str, rejeitada: bool) -> None:
    verbo = "rejeitada" if rejeitada else "devolvida para ajustes"
    corpo = (
        "Olá!\n\n"
        f"Sua análise do artigo '{analise.artigo.titulo[:120]}' foi {verbo} "
        "pela curadoria.\n\n"
        f"Motivo: {motivo or '(não informado)'}\n\n"
        "Acesse a plataforma para revisar."
    )
    _enviar(f"[AnCo] Sua análise foi {verbo}", corpo, [analise.analista.email])


def notificar_resenha_publicada(resenha: Resenha) -> None:
    autor = resenha.analise.analista
    corpo = (
        "Olá!\n\n"
        "Sua resenha crítica do artigo "
        f"'{resenha.analise.artigo.titulo[:120]}' foi confirmada pela curadoria "
        "e está publicada no acervo."
    )
    _enviar("[AnCo] Sua resenha foi publicada", corpo, [autor.email])
