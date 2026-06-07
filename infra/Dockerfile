FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.lock ./

# Instala dependencias a partir do lockfile (versoes fixas, build reproduzivel)
# e o proprio pacote em modo editavel sem re-resolver as deps. O stub de
# `config` deixa o setuptools achar o pacote; o codigo real entra via COPY
# abaixo (e via bind-mount em dev). Regenerar o lock: ver docs/DEPLOY.md.
RUN mkdir -p config && touch config/__init__.py \
    && pip install --upgrade pip \
    && pip install -r requirements.lock \
    && pip install -e . --no-deps

COPY . .

# Gera o CSS de produção (baixa o binário do Tailwind na primeira execução)
RUN python -m pytailwindcss -i static/css/input.css -o static/css/output.css --minify

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
