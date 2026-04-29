from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Núcleo"

    def ready(self) -> None:
        from . import signals  # noqa: F401  — registra receivers

        # Dashboard do admin home (Fase 6)
        from .admin_dashboard import instalar_dashboard

        instalar_dashboard()
