"""
Signals do app core.

- Ao criar SolicitacaoCadastro: envia e-mail aos curadores.
- Ao mudar status de SolicitacaoCadastro para `aprovada`: promove o usuario
  para `analista` e envia e-mail de boas-vindas.
- Ao mudar para `rejeitada`: envia e-mail informando a razao.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
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
    assunto = "[AnCo] Nova solicitação de promoção"
    url_admin = f"{settings.BASE_URL}" + reverse(
        "admin:core_solicitacaocadastro_change",
        args=[solicitacao.pk],
    )
    corpo = (
        f"Usuário {solicitacao.usuario} solicitou promoção a analista.\n\n"
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
    user = solicitacao.usuario
    if user.papel != User.Papel.CURADOR:  # nao rebaixa curador
        user.papel = User.Papel.ANALISTA
        user.save(update_fields=["papel"])
    if user.email:
        send_mail(
            "[AnCo] Sua solicitação foi aprovada",
            (
                "Olá!\n\n"
                "Sua solicitação foi aprovada — você agora pode criar e revisar análises "
                "no acervo da AnCo.\n\n"
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
    motivo = (solicitacao.motivo_rejeicao or "").strip()
    corpo_motivo = f"\nMotivo informado pelo curador:\n{motivo}\n" if motivo else ""
    send_mail(
        "[AnCo] Sua solicitação foi analisada",
        (
            "Olá!\n\n"
            "Sua solicitação de promoção a analista não foi aprovada neste momento."
            f"{corpo_motivo}\n"
            "Em caso de dúvida, entre em contato com a curadoria."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@anco.local"),
        recipient_list=[user.email],
        fail_silently=True,
    )
