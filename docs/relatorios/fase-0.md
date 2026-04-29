# Relatório — Fase 0: Fundação

**Data**: 2026-04-29
**Branch**: `fase-0-fundacao`
**Commits**: 9 (de `e99bfad` a `7657dad`)

## O que foi entregue

- Repositório Git inicializado com branch `main` e branch de trabalho `fase-0-fundacao`; `.gitignore` cobrindo Python, Django, Docker, ambientes e caches de lint/teste.
- `pyproject.toml` com `setuptools` build, dependências runtime mínimas (Django 5.1, django-environ, psycopg, gunicorn) e dev (pytest, pytest-django, pytest-cov, pytest-factoryboy, factory-boy, ruff). Ruff configurado (line-length 100, regras E/F/W/I/UP/B/SIM); pytest aponta para `config.settings.dev` com `--reuse-db`; coverage com `omit` para migrations, wsgi/asgi, prod settings.
- Projeto Django em `config/`:
  - `settings/base.py` — comum (Postgres via env, Redis cache, pt-br/America/Bahia)
  - `settings/dev.py` — `DEBUG=True`, e-mail no console
  - `settings/prod.py` — `SECURE_*` (HSTS 1 ano, SSL redirect, secure cookies), SMTP via env, logging estruturado
  - `urls.py` com `/admin` e endpoint `/healthz` (smoke público)
  - `wsgi.py`/`asgi.py` apontando para `prod` por padrão
  - `manage.py` apontando para `dev`
- `.env.example` versionado com variáveis da Fase 0 e referências comentadas para fases seguintes (OAuth, SMTP, S3, Wayback).
- `infra/Dockerfile` baseado em `python:3.12-slim` com `libpq-dev`/`build-essential`, instala o projeto em modo editável.
- `infra/docker-compose.yml` mínimo (web + db Postgres 16 + cache Redis 7) com healthchecks, `depends_on` condicional e volume `pgdata`.
- `tests/test_smoke.py` com 3 testes: `manage.py check`, conexão com Postgres e endpoint `/healthz`.
- `.github/workflows/ci.yml`: jobs `lint` (ruff check + format) e `test` (Postgres+Redis services, pytest com `--cov-fail-under=70`).
- `README.md` com bootstrap local, comandos úteis e tabela de roadmap das 8 fases.

## Critério de aceite (da especificação §10 — Fase 0)

- [x] Estrutura Django + Docker Compose
- [x] Postgres, Redis (Caddy adiado — ver "Desvios")
- [x] Settings dividido (base/dev/prod)
- [x] CI: lint (ruff) + testes (pytest-django)
- [x] README com bootstrap local

## Decisões tomadas

- **Ferramenta de empacotamento**: `setuptools` (com `pyproject.toml`) em vez de Poetry/PDM. Razão: menor superfície, suficiente para Django, sem necessidade de lock file dedicado nesta fase.
- **Versão Django fixada em 5.0.x–5.1.x**: pin conservador (`>=5.0,<5.2`) para evitar quebras pelo 6.0 antes de termos cobertura adequada.
- **psycopg 3 (binary)**: em vez de `psycopg2-binary` legado. Compatível com Django 5.x e mantido oficialmente.
- **Endpoint `/healthz`**: adicionado fora do plano original como smoke público — usado no teste de fumaça e útil para Caddy/load balancer em fases posteriores.
- **`config/settings/prod.py` excluído do coverage**: arquivo só tem configuração, executa apenas em produção real; testar exigiria mock pesado com pouco valor. Mantido no escopo de ruff.
- **`STATICFILES_DIRS` removido do base.py**: o diretório `static/` está vazio na Fase 0; manter o setting causaria warning W004. Reativaremos quando houver assets estáticos (Fase 3+).
- **Identidade Git**: configurada em `/tmp/gitconfig-claude` via `GIT_CONFIG_GLOBAL`, não em `~/.gitconfig`, para não modificar configuração do host.
- **Stub de `config/__init__.py` no Dockerfile**: necessário para `pip install -e .` antes do `COPY . .` final, mantendo o cache de build válido.

## Desvios da especificação

- **Caddy ausente do `docker-compose.yml`**.
  - Especificação (§3.3, §10): Caddy listado entre os serviços do compose desde a Fase 0.
  - Feito: serviço Caddy adiado para a Fase 7 (deploy em produção).
  - Por quê: usuário aprovou explicitamente o escopo "mínimo: web + db + cache" antes da implementação. Em desenvolvimento local acessamos `:8000` direto. Caddy só agrega valor quando há TLS/proxy reverso, o que é exigência de produção.
- **Worker `django-q2` ausente do compose**.
  - Especificação (§3.3): worker listado entre os serviços.
  - Feito: adiado para a Fase 4, quando o sorteio assíncrono de revisores entra em cena.
  - Por quê: `django-q2` não está em `pyproject.toml` ainda (a fase não exigia). Adicionar serviço sem dependência causaria container em loop de erro.
- **`STATICFILES_DIRS` removido**: ver "Decisões tomadas".

## Dívida técnica deixada

Nenhuma dívida intencional. Itens marcados na seção "Pendências para o usuário" são pré-requisitos externos, não dívida técnica.

## Métricas

- **Cobertura de testes**: 100% (40/40 statements no escopo coberto — `apps/`, `config/` exceto `prod.py`, `wsgi.py`, `asgi.py`).
- **Linhas adicionadas**: 713 (fora documentos pré-existentes — `CLAUDE.md`, `ESPECIFICACAO.md` e JSON legado, que entraram no repo no commit inicial mas já existiam no diretório).
- **Arquivos criados**: 22 (excluindo pré-existentes).
- **Tempo aproximado da fase**: ~16 minutos do primeiro ao último commit.
- **Verificação end-to-end**: 10/10 passos do plano `:white_check_mark:` (build, up, migrate, check, healthz HTTP 200, ruff check, ruff format, pytest+cov, YAML CI válido, branch com 9 commits atômicos).

## Pendências para o usuário

Antes de iniciar a Fase 1, **não-bloqueantes** (a Fase 1 pode começar sem elas, mas estes itens permanecem em aberto):

1. **Definir nome próprio da plataforma** — §15.2 da especificação. Atualmente o repo se chama `anco-plataforma`; verbose names em pt-BR ainda usam "AnCo / Análise Cognitiva" genericamente. Se houver decisão de marca antes da Fase 5 (acervo público), aplicaremos consistentemente.
2. **Criar repositório no GitHub** (ou outro provider) e adicionar como remote — destrava a execução do CI versionado em `.github/workflows/ci.yml`. Comandos:
   ```bash
   git remote add origin <URL>
   git push -u origin main
   git push -u origin fase-0-fundacao
   ```
3. **Revisar o ownership do diretório**: o ambiente atual mistura UID `root` (CLAUDE.md, docs/, novo código) com UID `anco-paulovicente` (diretório raiz). Funcional, mas uniformizar para `anco-paulovicente:anco-paulovicente` antes do deploy facilita operação. Sugestão (manual, fora do escopo do agente): `sudo chown -R anco-paulovicente:anco-paulovicente .`
4. **Revisar o domínio temporário vs definitivo**: o repo está em `anco.paulovicente.pro.br/` — adequado para staging/dev, mas o §9.3 da especificação prevê migração para domínio institucional com redirect permanente.

**Aprovação para iniciar a Fase 1** (Núcleo de dados e admin) é o próximo passo.
