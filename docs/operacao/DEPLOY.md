# Deploy — guia de produção

Procedimento para levar a AnCo a produção. Cobre a primeira instalação
e atualizações subsequentes. Pré-requisitos do servidor estão em §1.

## 1. Pré-requisitos do servidor

- Ubuntu 22.04 ou similar com Docker Engine + Docker Compose v2.
- Domínio com DNS apontando para o IP do servidor.
- Portas 80 e 443 liberadas para o Caddy obter o certificado Let's Encrypt.
- Mínimo 2 GB RAM (4 GB se a Fase 8 for ativada — embeddings).
- Pelo menos 20 GB de disco (banco + backups locais).

## 2. Configuração inicial

### 2.1. Variáveis de ambiente

Copie e ajuste:

```bash
cp .env.example .env
# Editar:
DJANGO_SECRET_KEY=<gerar com `python -c "import secrets; print(secrets.token_urlsafe(50))"`>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=anco.paulovicente.pro.br
POSTGRES_PASSWORD=<senha forte>
GOOGLE_OAUTH_CLIENT_ID=<obtido no Google Cloud Console>
GOOGLE_OAUTH_CLIENT_SECRET=<idem>
EMAIL_HOST=smtp.example.org
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=noreply@anco.paulovicente.pro.br
BASE_URL=https://anco.paulovicente.pro.br
ANCO_DOMAIN=anco.paulovicente.pro.br
ANCO_ADMIN_EMAIL=paulovicente.ifba@gmail.com
SENTRY_DSN=<opcional; deixar vazio se não usar>
BACKUP_S3_BUCKET=anco-backups
BACKUP_S3_ENDPOINT=https://s3.eu-central-1.amazonaws.com
```

> **Settings de prod**: `DJANGO_SETTINGS_MODULE=config.settings.prod`
> deve estar no ambiente do container web. Em produção,
> definir em `.env` ou no `command` do compose.

### 2.2. Build e subida com profile `prod`

```bash
docker compose -f infra/docker-compose.yml \
    --profile worker --profile prod \
    up -d --build
```

Isso sobe: `db`, `cache`, `web`, `worker`, `caddy` (que termina TLS).

### 2.3. Migrate, collectstatic, fixture, schedules, superuser

```bash
docker compose -f infra/docker-compose.yml exec web python manage.py migrate
docker compose -f infra/docker-compose.yml exec web python manage.py collectstatic --noinput
docker compose -f infra/docker-compose.yml exec web python manage.py loaddata vocabularios_iniciais
docker compose -f infra/docker-compose.yml exec web python manage.py setup_q_schedules
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser
```

### 2.4. Configurar `Site` (id=1)

Acesse `/admin/sites/site/1/change/` e atualize `domain` para o domínio
real (ex: `anco.paulovicente.pro.br`). Necessário para o allauth e para
URLs absolutas em e-mails.

### 2.5. Configurar OAuth Google

No Google Cloud Console, criar Client ID "Web application":
- Authorized redirect URIs: `https://anco.paulovicente.pro.br/accounts/google/login/callback/`

Copiar `client_id` e `secret` para o `.env` e reiniciar `web`.

### 2.6. Migrar legado (uma vez)

```bash
docker compose -f infra/docker-compose.yml exec web python manage.py migrate_legacy
```

Importa os 1.443 registros do JSON legado.

## 3. Atualização (deploy contínuo)

```bash
# 1. Pull da nova versão
git pull --rebase

# 2. Backup defensivo antes de subir mudanças
docker compose -f infra/docker-compose.yml exec web bash /app/infra/backup/run.sh

# 3. Build da nova imagem
docker compose -f infra/docker-compose.yml --profile worker --profile prod build

# 4. Migrations
docker compose -f infra/docker-compose.yml --profile worker --profile prod \
    run --rm web python manage.py migrate

# 5. Static files
docker compose -f infra/docker-compose.yml --profile worker --profile prod \
    run --rm web python manage.py collectstatic --noinput

# 6. Sobe nova versão (zero-downtime razoável com healthchecks)
docker compose -f infra/docker-compose.yml --profile worker --profile prod up -d
```

## 3-bis. Dependências e lockfile (build reproduzível)

As dependências estão declaradas em `pyproject.toml` (com ranges, ex.: `django>=5.0,<5.2`),
mas **a instalação usa o `requirements.lock`** — versões 100% fixas, geradas com
`pip-compile`. Isso garante que cada build instale exatamente os mesmos pacotes
(o Dockerfile e o CI instalam `-r requirements.lock` e depois `pip install -e . --no-deps`).

**Quando regenerar o lock** (após editar dependências no `pyproject.toml`, ou para
atualizar versões de segurança), rode dentro do mesmo Python da imagem (3.12):

```bash
docker run --rm -v "$PWD":/app -w /app python:3.12-slim bash -c "
  apt-get update -qq && apt-get install -y -qq build-essential libpq-dev
  pip install -q pip-tools
  pip-compile --extra dev --output-file requirements.lock pyproject.toml
"
```

Depois rebuilde a imagem e rode os testes (CI valida). Se o `ruff` mudar de versão
no lock, atualize o pin em `.github/workflows/ci.yml` (job *Lint*) e rode
`ruff format .` para reformatar o repositório com a nova versão.

## 4. Backup automatizado

Cron do host (não do container) executa o script:

```bash
# /etc/cron.d/anco-backup
0 3 * * * deploy cd /srv/anco && \
    docker compose -f infra/docker-compose.yml exec -T web bash /app/infra/backup/run.sh \
    >> /var/log/anco-backup.log 2>&1
```

O `setup_q_schedules` cuida dos schedules internos (verificar links,
re-sortear revisões expiradas). Backup é externo porque depende do
volume do host.

## 5. Logs e observabilidade

- **Logs do web**: JSON estruturado em stdout. Coletar com Loki, Vector
  ou similar. `docker compose logs -f web` para tail manual.
- **Sentry**: DSN configurada via `SENTRY_DSN`. Captura exceções e logs
  ERROR+. Self-hosted (GlitchTip) ou cloud — não importa.
- **Caddy**: log JSON em stdout. `docker compose logs caddy` para ver
  requisições / certificados.
- **Métricas do worker**: `/admin/django_q/` mostra fila, sucessos,
  falhas e schedules.

## 6. Healthcheck

Endpoint `https://anco.paulovicente.pro.br/healthz` retorna `200 ok` se
o web está vivo. Use em uptime monitors (Uptime Kuma, BetterStack).

## 7. Plano de redirecionamento na migração de domínio

Conforme spec §9.3: ao migrar do domínio temporário para o oficial,
manter o antigo respondendo com redirect permanente por **mínimo 12
meses** para não quebrar citações já feitas:

```caddy
anco.paulovicente.pro.br {
    redir https://novo-dominio-institucional.tld{uri} permanent
}
```

Atualizar `BASE_URL` e `ANCO_DOMAIN` no `.env` do novo servidor antes
de cortar o tráfego.

## 8. Modo manutenção

Para janelas de manutenção sem mostrar erros HTTP:

```bash
# Ativar
docker compose -f infra/docker-compose.yml stop web worker
# (Caddy continua de pé; pode-se servir uma página estática via
# `handle_errors` no Caddyfile)

# Restaurar
docker compose -f infra/docker-compose.yml --profile worker --profile prod up -d
```

## 9. Rollback

Se uma migration ou deploy quebrou:

1. Restaurar dump pré-deploy (`/tmp/pre-restore-snapshot.dump`, ver
   [RESTORE.md](RESTORE.md) §3.2).
2. `git checkout <tag-anterior>`.
3. Rebuild + up.

Por isso: **sempre** `manage.py backup_db` antes de migration nova.

---

**Última revisão**: 2026-04-29.
