"""
Signals do app core.

- Ao criar SolicitacaoCadastro: envia e-mail aos curadores.
- Ao mudar status de SolicitacaoCadastro para `aprovada`: promove o usuario
  para `analista` e envia e-mail de boas-vindas.
- Ao mudar para `rejeitada`: envia e-mail informando a razao.
- Ao apagar EmailAddress primary: reatribui trabalho do user para a
  Equipe AnCo e apaga o User.
"""

from __future__ import annotations

import logging
from threading import local

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from .models import SolicitacaoCadastro

logger = logging.getLogger(__name__)
User = get_user_model()


def _emails_curadores() -> list[str]:
    return list(
        User.objects.filter(papel=User.Papel.CURADOR, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


@receiver(pre_save, sender=SolicitacaoCadastro)
def _capturar_status_anterior(sender, instance: SolicitacaoCadastro, **kwargs):
    """Salva o status pre-save para o post_save comparar e detectar transicao."""
    if instance.pk:
        try:
            anterior = SolicitacaoCadastro.objects.get(pk=instance.pk)
            instance._status_anterior = anterior.status
        except SolicitacaoCadastro.DoesNotExist:
            instance._status_anterior = None
    else:
        instance._status_anterior = None


@receiver(post_save, sender=SolicitacaoCadastro)
def _notificar_e_promover(sender, instance: SolicitacaoCadastro, created: bool, **kwargs):
    """
    Reage a mudancas de SolicitacaoCadastro:

    - `created=True`: notifica curadores por e-mail.
    - status: pendente -> aprovada: promove user para analista + e-mail boas-vindas.
    - status: pendente -> rejeitada: e-mail informativo.
    """
    if created:
        _enviar_email_para_curadores(instance)
        return

    anterior = getattr(instance, "_status_anterior", None)
    if anterior == instance.status:
        return  # nao houve transicao

    if instance.status == SolicitacaoCadastro.Status.APROVADA:
        _aprovar_e_promover(instance)
    elif instance.status == SolicitacaoCadastro.Status.REJEITADA:
        _enviar_email_rejeicao(instance)


def _enviar_email_para_curadores(solicitacao: SolicitacaoCadastro) -> None:
    destinatarios = _emails_curadores()
    if not destinatarios:
        logger.warning(
            "Solicitacao %s criada mas nao ha curadores ativos com e-mail.",
            solicitacao.pk,
        )
        return
    tipo_label = solicitacao.get_tipo_display().lower()
    assunto = f"[AnCo] Nova solicitação de {tipo_label}"
    url_admin = f"{settings.BASE_URL}" + reverse(
        "admin:core_solicitacaocadastro_change",
        args=[solicitacao.pk],
    )
    corpo = (
        f"Usuário {solicitacao.usuario} solicitou habilitação como {tipo_label}.\n\n"
        f"Vínculo institucional: {solicitacao.usuario.vinculo_institucional}\n"
        f"Justificativa:\n{solicitacao.justificativa}\n\n"
        f"Aprovar/rejeitar no admin: {url_admin}\n"
    )
    send_mail(
        assunto,
        corpo,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@anco.local"),
        recipient_list=destinatarios,
        fail_silently=True,
    )


def _aprovar_e_promover(solicitacao: SolicitacaoCadastro) -> None:
    """Efeito da aprovação varia conforme o tipo da solicitação."""
    user = solicitacao.usuario
    tipo_label = solicitacao.get_tipo_display().lower()
    if solicitacao.tipo == SolicitacaoCadastro.Tipo.ANALISTA:
        # Promove a analista (não rebaixa curador)
        if user.papel != User.Papel.CURADOR:
            user.papel = User.Papel.ANALISTA
            user.save(update_fields=["papel"])
    elif solicitacao.tipo == SolicitacaoCadastro.Tipo.REVISOR:
        user.revisor_aprovado = True
        user.save(update_fields=["revisor_aprovado"])
    if user.email:
        send_mail(
            f"[AnCo] Sua solicitação de {tipo_label} foi aprovada",
            (
                "Olá!\n\n"
                f"Sua solicitação para atuar como {tipo_label} foi aprovada.\n\n"
                f"Acesse: {settings.BASE_URL}/\n"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@anco.local"),
            recipient_list=[user.email],
            fail_silently=True,
        )


def _enviar_email_rejeicao(solicitacao: SolicitacaoCadastro) -> None:
    user = solicitacao.usuario
    if not user.email:
        return
    tipo_label = solicitacao.get_tipo_display().lower()
    motivo = (solicitacao.motivo_rejeicao or "").strip()
    corpo_motivo = f"\nMotivo informado pelo curador:\n{motivo}\n" if motivo else ""
    send_mail(
        f"[AnCo] Sua solicitação de {tipo_label} foi analisada",
        (
            "Olá!\n\n"
            f"Sua solicitação para atuar como {tipo_label} não foi aprovada neste momento."
            f"{corpo_motivo}\n"
            "Em caso de dúvida, entre em contato com a curadoria."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@anco.local"),
        recipient_list=[user.email],
        fail_silently=True,
    )


# ---------------------------------------------------------------------------
# Apagar EmailAddress primary => apaga User (com reatribuição de trabalho)
# ---------------------------------------------------------------------------

# Flag thread-local pra evitar recursão: ao apagar User, o cascade apaga
# outros EmailAddress dele, que disparariam este signal de novo.
_em_cascata = local()

USERNAME_EQUIPE_ANCO = "curadoria-bibliotecaria"


def _equipe_anco_user():
    """Retorna (ou cria) o user 'curadoria-bibliotecaria' que herda trabalho órfão."""
    user, criado = get_user_model().objects.get_or_create(
        username=USERNAME_EQUIPE_ANCO,
        defaults={
            "email": "bibliotecaria@anco.local",
            "nome_exibicao": "Equipe AnCo",
            "papel": get_user_model().Papel.ANALISTA,
            "eh_legado": True,
            "is_active": False,
        },
    )
    return user


def _reatribuir_trabalho_para_equipe(user) -> dict:
    """
    Reatribui FKs PROTECT do user para a Equipe AnCo. Retorna contagens.

    - Analise.analista → equipe (pula artigos onde equipe já tem análise:
      UniqueConstraint(artigo, analista) — análise duplicada é apagada com log)
    - Revisao.revisor (concluídas) → equipe (preserva histórico)
    - Revisao.revisor (pendentes) → delete (cancela revisão sem parecer)
    """
    from apps.acervo.models import Analise, Revisao

    equipe = _equipe_anco_user()
    if equipe.pk == user.pk:
        return {
            "analises_movidas": 0, "analises_descartadas_conflito": 0,
            "revisoes_canceladas": 0, "revisoes_movidas": 0,
        }

    # Análises: reatribui uma a uma, respeitando UniqueConstraint(artigo, analista).
    movidas = 0
    descartadas = 0
    artigos_equipe = set(
        Analise.objects.filter(analista=equipe).values_list("artigo_id", flat=True)
    )
    for analise in Analise.objects.filter(analista=user):
        if analise.artigo_id in artigos_equipe:
            # Equipe já tem análise desse artigo → descarta a duplicada
            logger.warning(
                "Análise %s (artigo %s) descartada: Equipe AnCo já tem análise do mesmo artigo.",
                analise.pk, analise.artigo_id,
            )
            analise.delete()
            descartadas += 1
        else:
            analise.analista = equipe
            analise.save(update_fields=["analista"])
            artigos_equipe.add(analise.artigo_id)
            movidas += 1

    # Revisões pendentes: cancela (não há parecer ainda).
    canceladas, _ = Revisao.objects.filter(
        revisor=user, concluido_em__isnull=True
    ).delete()

    # Revisões concluídas: move (preserva histórico).
    # UniqueConstraint(analise, revisor, tipo): se equipe já tem revisão
    # da mesma análise+tipo, pula a duplicada.
    movidas_rev = 0
    descartadas_rev = 0
    for rev in Revisao.objects.filter(revisor=user):
        if Revisao.objects.filter(
            analise=rev.analise, revisor=equipe, tipo=rev.tipo
        ).exists():
            logger.warning(
                "Revisão %s (analise %s) descartada: Equipe AnCo já tem revisão.",
                rev.pk, rev.analise_id,
            )
            rev.delete()
            descartadas_rev += 1
        else:
            rev.revisor = equipe
            rev.save(update_fields=["revisor"])
            movidas_rev += 1

    return {
        "analises_movidas": movidas,
        "analises_descartadas_conflito": descartadas,
        "revisoes_canceladas": canceladas,
        "revisoes_movidas": movidas_rev,
        "revisoes_descartadas_conflito": descartadas_rev,
    }


@receiver(post_delete, sender=EmailAddress)
def _apagar_user_ao_apagar_email_primary(sender, instance: EmailAddress, **kwargs):
    """
    Apagar um EmailAddress marcado como primary remove o User dono também.
    Trabalho (análises e revisões) é movido para 'Equipe AnCo' antes.

    Salvaguardas:
    - Só age se o email apagado era `primary=True`.
    - Não apaga superuser (proteção contra perda de admin).
    - Não apaga o próprio user 'Equipe AnCo'.
    - Flag thread-local evita recursão durante o cascade.
    """
    if getattr(_em_cascata, "ativo", False):
        return
    if not instance.primary:
        return
    User = get_user_model()
    if not instance.user_id:
        return
    user = User.objects.filter(pk=instance.user_id).first()
    if not user:
        return  # já apagado via cascade
    if user.is_superuser:
        logger.warning(
            "EmailAddress primary de superuser %s apagado mas User preservado.",
            user.email,
        )
        return
    if user.username == USERNAME_EQUIPE_ANCO:
        logger.warning("Tentativa de apagar Equipe AnCo via EmailAddress ignorada.")
        return

    _em_cascata.ativo = True
    try:
        with transaction.atomic():
            stats = _reatribuir_trabalho_para_equipe(user)
            user.delete()
        logger.info(
            "Usuário %s apagado por remoção de EmailAddress primary. Stats: %s",
            user.email, stats,
        )
    finally:
        _em_cascata.ativo = False


def reatribuir_trabalho_antes_de_apagar_user(user) -> dict | None:
    """
    Chamada pelo `User.delete()` antes da deleção real. Reatribui o trabalho
    do user à Equipe AnCo para liberar as FKs PROTECT do Collector.

    Retorna stats se reatribuiu, ou None se a reatribuição foi pulada
    (superuser, equipe, legado, ou em cascata).
    """
    if getattr(_em_cascata, "ativo", False):
        return None
    if user.is_superuser:
        logger.warning(
            "Tentativa de apagar superuser %s — trabalho NÃO reatribuído.",
            user.email,
        )
        return None
    if user.username == USERNAME_EQUIPE_ANCO:
        return None
    if user.eh_legado:
        return None  # contas sintéticas da migração; cascade direto
    stats = _reatribuir_trabalho_para_equipe(user)
    logger.info(
        "Usuário %s será apagado: trabalho reatribuído à Equipe AnCo. Stats: %s",
        user.email, stats,
    )
    return stats
