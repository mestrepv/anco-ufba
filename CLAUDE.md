# CLAUDE.md

Instruções operacionais para o Claude Code trabalhando neste repositório.
Leia este arquivo no início de cada sessão.

---

## 1. Contexto do projeto

Plataforma colaborativa de pesquisa para catalogar e analisar literatura
científica sobre **Análise Cognitiva (AnCo)**. Substitui um fluxo atual
baseado em Google Forms + Sheets. Sistema com cadastro institucional,
revisão por pares (double review) e acervo público citável.

**Documento canônico de especificação**: `docs/ESPECIFICACAO.md`.
Em caso de conflito entre este `CLAUDE.md` e a especificação, a
especificação prevalece para decisões de produto. Este arquivo prevalece
para decisões de processo.

---

## 2. Princípio número 1: trabalho faseado

O projeto é dividido em **8 fases** (0 a 7) descritas na seção 8 da
especificação. Você implementa **uma fase por vez** e **para ao final
de cada fase aguardando aprovação humana** antes de iniciar a próxima.

- Nunca pule fases.
- Nunca implemente código de fases futuras "para adiantar".
- Se descobrir que uma fase depende de algo de uma fase futura, pare e
  proponha ajuste de escopo ao usuário em vez de implementar
  silenciosamente.

Ao terminar uma fase, produza um **Relatório de Fim de Fase** (ver §7).

---

## 3. Stack e convenções técnicas

- Python 3.12, Django 5.x, PostgreSQL 16, Redis, Caddy 2, Docker Compose.
- Frontend: templates Django + HTMX + Alpine.js + Tailwind CSS.
- Auth: `django-allauth` com Google OAuth.
- Histórico: `django-simple-history`.
- Tasks assíncronas: `django-q2`.
- Testes: `pytest-django` + `pytest-factoryboy`.
- Lint/format: `ruff` (substitui black, flake8, isort).
- Type hints onde melhorar legibilidade; **não** force tipagem em todo
  lugar.

### 3.1. Estrutura de diretórios esperada
```
.
├── apps/
│   ├── core/          # User estendido, mixins, utils
│   ├── acervo/        # Artigo, Análise, Revisão
│   ├── vocabulario/   # Vocabulários controlados
│   └── publico/       # Views do acervo público
├── config/
│   ├── settings/      # base.py, dev.py, prod.py
│   ├── urls.py
│   └── wsgi.py
├── templates/
├── static/
├── docs/
├── infra/
│   ├── docker-compose.yml
│   ├── Caddyfile
│   └── backup/
├── tests/
├── manage.py
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

### 3.2. Settings
Sempre use `django-environ` para ler `.env`. Nunca *hardcode* segredos.
Crie `.env.example` versionado; `.env` no `.gitignore`.

### 3.3. Modelos
- `Meta` com `verbose_name` e `verbose_name_plural` em pt-BR.
- `__str__` significativo para todo modelo (admin depende disso).
- `db_index=True` em campos de filtro frequente.
- Restrições de integridade preferencialmente via `constraints`
  (UniqueConstraint, CheckConstraint), não via signals.

### 3.4. Views
Prefira **Class-Based Views** quando aproveitar mixins do Django;
function-based para casos triviais. Evite views gigantes — extraia
lógica de negócio para `services.py` por app.

### 3.5. Templates
Componentes reutilizáveis em `templates/_components/`. Use HTMX para
interatividade leve (auto-save, busca facetada, paginação infinita)
antes de pensar em JS custom.

---

## 4. Padrões de commit

Convenção: **Conventional Commits** simplificado.

```
<tipo>(<escopo>): <descrição curta>

[corpo opcional explicando o porquê]

[rodapé opcional: refs, breaking changes]
```

Tipos aceitos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`,
`style`, `perf`.

Escopo = nome do app ou área (`acervo`, `auth`, `infra`, `migracao`).

**Tamanho do commit**: pequeno e atômico. Um commit = uma ideia. Se você
precisa usar "e" na descrição, provavelmente são dois commits.

**Exemplos bons**:
- `feat(acervo): adiciona modelo Análise com histórico de versões`
- `fix(migracao): trata anos inválidos como null`
- `test(auth): cobre validação de domínio institucional`

**Exemplos ruins**:
- `update` (vago)
- `feat: vários ajustes` (não atômico)
- `WIP` (não comitar WIP em main)

Idioma: **português brasileiro** nas mensagens. Código e identificadores
em inglês quando for convenção da framework (`models.py`, `views.py`,
`Meta`, `verbose_name`); termos de domínio em português
(`Analise`, `Revisao`, `Curador`).

---

## 5. Branches e fluxo Git

- `main` é sempre estável (passa em CI).
- Trabalho em branches `fase-N-<slug-curto>` (ex: `fase-1-modelagem-base`).
- Ao terminar uma fase, abrir Pull/Merge Request com link para o
  Relatório de Fim de Fase.
- Squash merge para manter histórico limpo de `main`.
- Nunca fazer `git push --force` em `main`.

---

## 6. Testes

- Testes obrigatórios para: validações de modelo, services de domínio,
  fluxos críticos (sorteio de revisores, transição de status).
- Testes opcionais (mas bem-vindos) para: views simples, templates.
- Cobertura mínima por fase: **70%** nas linhas de código novo.
- Rode `pytest --cov` antes de declarar a fase concluída.
- Use factories (`pytest-factoryboy`), não fixtures hardcoded.
- Nomes de teste descritivos: `test_sorteio_exclui_autor_da_analise`,
  não `test_sorteio_1`.

---

## 7. Relatório de Fim de Fase

Ao concluir uma fase, gere `docs/relatorios/fase-N.md` com:

```markdown
# Relatório — Fase N: <Nome da fase>

## O que foi entregue
- <bullet por entrega>

## Critério de aceite (da especificação)
- [x] Item cumprido
- [ ] Item parcial — explicar

## Decisões tomadas
Decisões de implementação que não estavam no documento de
especificação e que valem registrar.

## Desvios da especificação
Casos onde implementei algo diferente do documento. Cada item com:
- O que a especificação dizia
- O que foi feito
- Por quê

## Dívida técnica deixada
Itens que decidi adiar conscientemente, com TODO no código.

## Métricas
- Cobertura de testes: X%
- Linhas adicionadas / removidas
- Tempo aproximado da fase

## Pendências para o usuário
- Configurar X antes de eu seguir para Fase N+1
- Revisar Y e me dizer se faz sentido
```

Sem este relatório, **não inicie a próxima fase**.

---

## 8. Comunicação durante o trabalho

### 8.1. Quando perguntar
- **Decisões de produto** não cobertas pela especificação: pergunte.
- **Tradeoffs de implementação** com impacto visível ao usuário: pergunte
  com 2-3 opções.
- **Detalhes técnicos sem impacto externo**: decida e documente no
  relatório.

### 8.2. Quando NÃO perguntar
- Convenções já definidas neste arquivo.
- Pequenos ajustes de nomenclatura, formatação, organização interna.
- Bibliotecas auxiliares pequenas (ex: usar `humanize` para datas).

### 8.3. Tom
Direto, técnico, sem exageros de polidez. Se discordar de algo na
especificação, diga e proponha alternativa — você é o implementador,
não um executor passivo.

---

## 9. Pontos de atenção específicos

### 9.1. Migração do legado (Fase 1)
Os 1.443 registros do JSON têm inconsistências catalogadas na §7.1 da
especificação. Antes de importar:
- Rode análise exploratória e produza `docs/migracao/analise_legado.md`
  com estatísticas reais (quantos sem DOI, quantos com ano inválido,
  quantas variantes de "Empirismo" etc.).
- Implemente o migrador como **idempotente** (rodar 2x não duplica).
- Loga tudo que normalizou; não silencie nada.

### 9.2. Fluxo de revisão (Fase 4)
Lógica de domínio densa. Antes de codar, escreva os testes do fluxo
completo (TDD aqui faz diferença). Casos a cobrir:
- Sorteio com revisores suficientes
- Sorteio com revisores insuficientes (fallback)
- Re-sorteio por prazo expirado
- Aprovação por 2 revisores → publicação
- 1 ajustes + 1 aprovação → volta para rascunho
- Revisor que é autor da análise é excluído
- Revisor que tem outra análise do mesmo artigo é excluído

### 9.3. Acervo público (Fase 5)
URLs **estáveis e citáveis** desde o dia 1. Mudança de URL depois quebra
citações. Padrão sugerido:
- `/acervo/` — listagem
- `/artigo/<doi-slug>/` — página do artigo
- `/analise/<id>/` — página da análise (id imutável)
- Slugs do DOI normalizados (sem `/` problemático).

---

## 10. O que NÃO fazer

- **Não** instale dependências sem propósito claro. Cada nova lib em
  `pyproject.toml` precisa de justificativa no commit.
- **Não** crie *abstractions* especulativas. Não use Design Pattern só
  por usar. Código simples primeiro; abstraia quando a duplicação
  realmente doer.
- **Não** suba código sem testes para áreas listadas como obrigatórias.
- **Não** comite `.env`, dumps de banco, PDFs do legado, secrets.
- **Não** use `print()` para debug em código entregue. Use `logging`.
- **Não** desabilite checks do CI para "passar mais rápido".
- **Não** reescreva a especificação por conta própria. Proponha mudanças
  ao usuário em vez disso.

---

## 11. Comandos úteis (referência rápida)

```bash
# Desenvolvimento
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell

# Testes e qualidade
docker compose exec web pytest
docker compose exec web pytest --cov
docker compose exec web ruff check .
docker compose exec web ruff format .

# Migração de dados
docker compose exec web python manage.py migrate_legacy --dry-run
docker compose exec web python manage.py migrate_legacy

# Backup manual
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql
```

---

## 12. Quando estiver em dúvida

Releia a especificação. Se a dúvida persistir, pergunte ao usuário com
contexto: o que está fazendo, qual a dúvida específica, quais opções
considera, qual sua recomendação.

Não invente. Não assuma. Pergunte.