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

# Em testes, sem retry para o serviço de embeddings (evita lentidão).
EMBEDDINGS_MAX_RETRIES = 1

# Quando rodando atras do Caddy (HTTPS proxy), manter URLs absolutas corretas.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Sem cache algum em dev — qualquer mudança reflete imediatamente.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Módulo Revisão ANCO ligado em dev/test (transição da separação ANCO × PRISMA).
# Em produção segue OFF (default em base.py) até a Fase B do plano.
ANCO_ATIVO = True
