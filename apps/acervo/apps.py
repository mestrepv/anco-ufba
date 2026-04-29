from django.apps import AppConfig


class AcervoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.acervo"
    label = "acervo"
    verbose_name = "Acervo"

    def ready(self) -> None:
        from . import signals  # noqa: F401  — registra receivers Fase 4
