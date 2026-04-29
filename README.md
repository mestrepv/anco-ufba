# AnCo — Plataforma de Análise Cognitiva

Plataforma colaborativa de pesquisa para catalogar e analisar literatura
científica sobre **Análise Cognitiva (AnCo)**. Substitui o fluxo atual
baseado em Google Forms + Sheets + Sites por um sistema com cadastro
institucional, revisão por pares (double review) e acervo público citável.

Especificação técnica completa: [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md).
Instruções operacionais para desenvolvimento: [`CLAUDE.md`](CLAUDE.md).

**Fase atual**: 0 / 7 — Fundação.

---

## Stack

- Python 3.12 + Django 5.x
- PostgreSQL 16
- Redis 7 (cache + fila de tasks)
- Docker Compose para desenvolvimento local
- Ruff (lint + format) e pytest (testes)

## Pré-requisitos

- Docker 24+ e Docker Compose v2+
- Git

## Bootstrap local

```bash
# 1. Copiar variáveis de ambiente
cp .env.example .env
# (edite .env e gere uma DJANGO_SECRET_KEY com `python -c "import secrets; print(secrets.token_urlsafe(50))"`)

# 2. Subir os containers
docker compose -f infra/docker-compose.yml up -d

# 3. Aplicar migrações
docker compose -f infra/docker-compose.yml exec web python manage.py migrate

# 4. Criar superusuário
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser

# 5. Acessar
#   App:    http://localhost:8000/
#   Admin:  http://localhost:8000/admin/
#   Health: http://localhost:8000/healthz
```

## Comandos úteis

```bash
# Testes e qualidade
docker compose -f infra/docker-compose.yml exec web pytest
docker compose -f infra/docker-compose.yml exec web pytest --cov
docker compose -f infra/docker-compose.yml exec web ruff check .
docker compose -f infra/docker-compose.yml exec web ruff format .

# Shell Django
docker compose -f infra/docker-compose.yml exec web python manage.py shell

# Logs
docker compose -f infra/docker-compose.yml logs -f web
```

Lista completa em [`CLAUDE.md` §11](CLAUDE.md).

## Roadmap

Implementação faseada em 8 fases (~3-4 semanas). Status vivo, checklist
e pendências em [`docs/ROADMAP.md`](docs/ROADMAP.md). Escopo canônico
em [§10 da especificação](docs/ESPECIFICACAO.md).

## Licença

A definir antes do lançamento. Conteúdo autoral hospedado segue
**Creative Commons Atribuição-NãoComercial 4.0 (CC-BY-NC 4.0)** conforme
[§7 da especificação](docs/ESPECIFICACAO.md). O código da plataforma
será publicado sob licença open source compatível.
