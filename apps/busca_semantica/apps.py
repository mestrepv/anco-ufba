from django.apps import AppConfig


class BuscaSemanticaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.busca_semantica"
    verbose_name = "Busca Semântica"

    def ready(self) -> None:
        import apps.busca_semantica.signals  # noqa: F401
