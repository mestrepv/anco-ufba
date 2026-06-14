"""
Settings base do projeto AnCo.

Configuracoes comuns a todos os ambientes. Especializacoes em dev.py e prod.py.
Le variaveis de ambiente via django-environ a partir do .env na raiz do projeto.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-default-only-for-build-time")

DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    # django-unfold — TEM que vir antes de django.contrib.admin
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    "simple_history",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_q",
    "apps.core",
    "apps.vocabulario",
    "apps.acervo",
    "apps.triagem",
    "apps.anco",
    "apps.publico",
    "apps.busca_semantica",
]

# django-q2 — broker Redis em prod, sync em dev/test (override em dev.py)
Q_CLUSTER = {
    "name": "anco",
    "workers": 2,
    "recycle": 500,
    "timeout": 60,
    "retry": 90,
    "compress": True,
    "save_limit": 250,
    "queue_limit": 500,
    "cpu_affinity": 1,
    "label": "AnCo Tasks",
    "redis": {
        "host": env("REDIS_HOST", default="cache"),
        "port": env.int("REDIS_PORT", default=6379),
        "db": env.int("REDIS_Q_DB", default=1),
    },
}

SITE_ID = 1

AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="anco"),
        "USER": env("POSTGRES_USER", default="anco"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://cache:6379/0"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploads de usuário (foto de perfil). Em produção, Caddy serve /media/*
# diretamente de MEDIA_ROOT (configurar bloco no Caddyfile).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

BASE_URL = env("BASE_URL", default="http://localhost:8000")

# URL canônica que aparece nas citações públicas (ABNT/APA). Independente
# de BASE_URL — em dev, BASE_URL pode ser um domínio de teste, mas a citação
# já mostra o domínio definitivo (anco.ufba.br) que receberá os links após
# a migração final de DNS.
URL_PUBLICA_CITAVEL = env("URL_PUBLICA_CITAVEL", default="https://anco.ufba.br")

# Serviço de embeddings (Fase 8)
EMBEDDINGS_URL = env("EMBEDDINGS_URL", default="http://embeddings:8080")
EMBEDDINGS_TIMEOUT = env.int("EMBEDDINGS_TIMEOUT", default=30)

# ----------------------------------------------------------------------
# Autenticacao (Fase 2)
# ----------------------------------------------------------------------

LOGIN_URL = "/accounts/login/"
# Apos OAuth, vai direto para a view de solicitacao; ela redireciona conforme
# o estado do usuario (leitor sem solicitacao -> form; leitor com solicitacao
# -> status; analista/curador -> home).
LOGIN_REDIRECT_URL = "/_pos_login/"
LOGOUT_REDIRECT_URL = "/"

# Lista de dominios institucionais aceitos. Sufixos comecando com "."
# casam o dominio e qualquer subdominio (`.edu.br` casa `usp.br`,
# `ufba.br`, mas tambem `lab.usp.br`). Strings sem ponto inicial casam
# exatamente.
ALLOWED_INSTITUTIONAL_DOMAINS = env.list(
    "ALLOWED_INSTITUTIONAL_DOMAINS",
    default=[
        ".edu",
        ".edu.br",
        ".ac.uk",
        "ufba.br",
        "ifba.edu.br",
        "uneb.br",
        "usp.br",
        "unicamp.br",
        "ufmg.br",
        "ufrj.br",
        "ufpe.br",
        "fiocruz.br",
        "senaicimatec.com.br",
    ],
)

# allauth — perfil minimo para auth via Google. Demais defaults bastam.
ACCOUNT_LOGIN_METHODS = {"email"}
# password1 precisa estar listado para o LoginForm manter o campo de senha
# (sem isso, allauth remove o campo e o login vira passwordless por codigo).
# Signup publico esta fechado em apps.core.adapters.AnCoAccountAdapter, entao
# este campo so afeta o LoginForm.
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = (
    "optional"  # cria EmailAddress (já verificado p/ OAuth) sem exigir confirmação
)
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_LOGOUT_ON_GET = False

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
    }
}

SOCIALACCOUNT_ADAPTER = "apps.core.adapters.AnCoSocialAccountAdapter"
ACCOUNT_ADAPTER = "apps.core.adapters.AnCoAccountAdapter"

# Pula a tela intermediária "Você está prestes a fazer login...": GET no
# /accounts/<provider>/login/ já redireciona direto pro provider. A proteção
# de CSRF da etapa intermediária é dispensada — o Google ainda exige consent
# explícito do usuário antes de devolver o token, então o risco é baixo.
SOCIALACCOUNT_LOGIN_ON_GET = True

# Rate limits do allauth (Fase 7). Override em dev pra nao atrapalhar.
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m",  # 5 tentativas falhas a cada 5 minutos por IP
    "login": "30/5m",
    "signup": "3/h",
    "send_email": "5/h",
}

# ---------------------------------------------------------------------------
# Admin (django-unfold) — paleta dourada da AnCo
# ---------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "AnCo — Curadoria",
    "SITE_HEADER": "AnCo",
    "SITE_SUBHEADER": "Painel de curadoria",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "THEME": None,  # None = respeita preferência do sistema; "light" ou "dark" força
    "COLORS": {
        # Paleta extraída do design system (var(--color-gold-deep) = #8C6520)
        "primary": {
            "50": "250 247 232",  # review-bg
            "100": "245 241 232",  # paper-2
            "200": "232 220 168",  # review-rule
            "300": "212 204 184",  # rule-strong
            "400": "184 134 44",  # gold
            "500": "140 101 32",  # gold-deep (principal)
            "600": "120 86 24",
            "700": "96 69 18",
            "800": "72 52 14",
            "900": "48 34 9",
            "950": "26 24 22",  # ink
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}
