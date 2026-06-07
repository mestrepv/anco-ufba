"""Signals da triagem.

`DecisaoTriagem.post_save`: quando `concluido_em` é setado -> dispara avaliação
do registro (consenso/divergência). O início da triagem (sorteio) é uma ação
explícita de UI (`tasks.iniciar_triagem`), não um signal.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import DecisaoTriagem

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DecisaoTriagem)
def _capturar_concluida(sender, instance: DecisaoTriagem, **kwargs):
    if instance.pk:
        try:
            instance._concluido_anterior = DecisaoTriagem.objects.get(pk=instance.pk).concluido_em
        except DecisaoTriagem.DoesNotExist:
            instance._concluido_anterior = None
    else:
        instance._concluido_anterior = None


@receiver(post_save, sender=DecisaoTriagem)
def _disparar_avaliacao(sender, instance: DecisaoTriagem, created: bool, **kwargs):
    if created:
        return
    if getattr(instance, "_concluido_anterior", None) is not None:
        return  # já estava concluída
    if instance.concluido_em is not None and instance.registro_id is not None:
        async_task("apps.triagem.tasks.task_avaliar_apos_triagem", instance.registro_id)
