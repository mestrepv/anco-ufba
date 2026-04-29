"""Settings de desenvolvimento."""

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = True

ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1", "localhost"]

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="dev-secret-key-not-for-production-use-only",
)

# Em dev e teste, executa tasks no proprio processo (sem worker).
Q_CLUSTER = {**Q_CLUSTER, "sync": True}  # noqa: F405
