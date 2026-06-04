from django.apps import AppConfig


class TriagemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.triagem"
    label = "triagem"
    verbose_name = "Triagem (PRISMA-ScR)"

    def ready(self) -> None:
        from . import signals  # noqa: F401  — registra receivers da triagem
