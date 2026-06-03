"""
Signals do app acervo.

- Resenha.post_save: status muda para `submetida` -> dispara sorteio cego.
- Revisao.post_save: `concluido_em` foi setado -> dispara avaliação da resenha.

Análises NÃO disparam sorteio (a revisão por pares vale só para resenhas; a
publicação da análise é ação explícita de um curador).

Todos os sinais usam `async_task` (django-q2). Em dev/teste com
`Q_CLUSTER.sync=True`, rodam no mesmo processo. Em prod, no worker.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import Resenha, Revisao

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Resenha: detecta transição para `submetida` -> sorteio cego
# ----------------------------------------------------------------------


@receiver(pre_save, sender=Resenha)
def _capturar_status_resenha(sender, instance: Resenha, **kwargs):
    if instance.pk:
        try:
            instance._status_anterior = Resenha.objects.get(pk=instance.pk).status
        except Resenha.DoesNotExist:
            instance._status_anterior = None
    else:
        instance._status_anterior = None


@receiver(post_save, sender=Resenha)
def _disparar_sorteio_resenha(sender, instance: Resenha, created: bool, **kwargs):
    anterior = getattr(instance, "_status_anterior", None)
    if anterior == Resenha.Status.SUBMETIDA:
        return  # idempotente
    if instance.status == Resenha.Status.SUBMETIDA:
        async_task("apps.acervo.tasks.task_sortear_revisores_cegos", instance.pk)


# ----------------------------------------------------------------------
# Revisao: dispara avaliação da resenha quando concluída
# ----------------------------------------------------------------------


@receiver(pre_save, sender=Revisao)
def _capturar_concluida_revisao(sender, instance: Revisao, **kwargs):
    if instance.pk:
        try:
            instance._concluido_anterior = Revisao.objects.get(
                pk=instance.pk
            ).concluido_em
        except Revisao.DoesNotExist:
            instance._concluido_anterior = None
    else:
        instance._concluido_anterior = None


@receiver(post_save, sender=Revisao)
def _disparar_avaliacao_ao_concluir(sender, instance: Revisao, created: bool, **kwargs):
    if created:
        return
    if getattr(instance, "_concluido_anterior", None) is not None:
        return  # já estava concluída
    if instance.concluido_em is not None and instance.resenha_id is not None:
        async_task(
            "apps.acervo.tasks.task_avaliar_apos_revisao_cega", instance.resenha_id
        )
