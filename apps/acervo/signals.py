"""
Signals do app acervo (Fase 4).

- Analise.post_save: status muda para `submetida` -> dispara sorteio.
- Revisao.post_save: `concluido_em` foi setado -> dispara avaliacao.

Todos os sinais usam `async_task` (django-q2). Em dev/teste com
`Q_CLUSTER.sync=True`, rodam no mesmo processo. Em prod, no worker.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import Analise, Revisao

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Analise: detecta transicao para `submetida`
# ----------------------------------------------------------------------


@receiver(pre_save, sender=Analise)
def _capturar_status_analise(sender, instance: Analise, **kwargs):
    if instance.pk:
        try:
            anterior = Analise.objects.get(pk=instance.pk)
            instance._status_anterior = anterior.status
        except Analise.DoesNotExist:
            instance._status_anterior = None
    else:
        instance._status_anterior = None


@receiver(post_save, sender=Analise)
def _disparar_sorteio_ao_submeter(sender, instance: Analise, created: bool, **kwargs):
    if created:
        return
    anterior = getattr(instance, "_status_anterior", None)
    if anterior == Analise.Status.SUBMETIDA:
        return  # idempotente
    if instance.status == Analise.Status.SUBMETIDA:
        async_task("apps.acervo.tasks.task_sortear_revisores", instance.pk)


# ----------------------------------------------------------------------
# Revisao: dispara avaliacao quando concluida
# ----------------------------------------------------------------------


@receiver(pre_save, sender=Revisao)
def _capturar_concluida_revisao(sender, instance: Revisao, **kwargs):
    if instance.pk:
        try:
            anterior = Revisao.objects.get(pk=instance.pk)
            instance._concluido_anterior = anterior.concluido_em
        except Revisao.DoesNotExist:
            instance._concluido_anterior = None
    else:
        instance._concluido_anterior = None


@receiver(post_save, sender=Revisao)
def _disparar_avaliacao_ao_concluir(sender, instance: Revisao, created: bool, **kwargs):
    if created:
        return
    anterior = getattr(instance, "_concluido_anterior", None)
    if anterior is not None:
        return  # ja estava concluida
    if instance.concluido_em is not None:
        async_task("apps.acervo.tasks.task_avaliar_apos_revisao", instance.analise_id)
