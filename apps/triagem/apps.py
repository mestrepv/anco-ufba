import contextlib

from django.apps import AppConfig


class TriagemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.triagem"
    label = "triagem"
    verbose_name = "Triagem (PRISMA-ScR)"

    def ready(self) -> None:
        # Receivers registrados na Fase 9.3 (sorteio/avaliação da triagem).
        # Fase 9.0/9.1: signals ainda não existe; scaffolding aditivo.
        with contextlib.suppress(ImportError):
            from . import signals  # noqa: F401
