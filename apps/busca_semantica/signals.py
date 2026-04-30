"""Signals que disparam geração de embedding após save de Artigo e Analise."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("busca_semantica")


def _dispatch(task_path: str, pk: int) -> None:
    """Enfileira a task no django-q2; falha silenciosa se o broker estiver offline."""
    try:
        from django_q.tasks import async_task

        async_task(task_path, pk)
    except Exception as exc:
        logger.warning("Não foi possível enfileirar %s(%d): %s", task_path, pk, exc)


@receiver(post_save, sender="acervo.Artigo")
def artigo_post_save(sender, instance, **kwargs) -> None:  # type: ignore[no-untyped-def]
    _dispatch("apps.busca_semantica.tasks.task_embedding_artigo", instance.pk)


@receiver(post_save, sender="acervo.Analise")
def analise_post_save(sender, instance, **kwargs) -> None:  # type: ignore[no-untyped-def]
    _dispatch("apps.busca_semantica.tasks.task_embedding_analise", instance.pk)
