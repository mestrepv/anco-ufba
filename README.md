# AnCo — Plataforma de Análise Cognitiva

Plataforma colaborativa para catalogação e análise crítica de literatura
científica sobre **Análise Cognitiva (AnCo)**. Substitui um fluxo legado
baseado em Google Forms + Sheets + Sites por um sistema com cadastro
institucional, vocabulário controlado, revisão por pares dupla e acervo
público citável, com busca semântica calibrável.

- **URL pública:** <https://anco.paulovicente.pro.br/>
- **Stack:** Python 3.12, Django 5.x, PostgreSQL 16 + pgvector, Redis 7,
  Caddy 2, Docker Compose
- **Status:** Fases 0–8 concluídas; calibração ativa da busca semântica
  em discussão (ver §5.2)
- **Licença:** conteúdo autoral em CC-BY-NC 4.0; código a definir antes
  do lançamento

> Documento de apoio ao artigo submetido ao **II Congresso de Difusão
> do Conhecimento**. Para o contrato técnico canônico, ver
> [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md). Para fundamentação
> conceitual da AnCo, ver [docs/tutorial_base_anco.md](docs/tutorial_base_anco.md).

---

## Sumário

1. [Contexto e motivação — de planilha a plataforma](#1-contexto-e-motivação--de-planilha-a-plataforma)
2. [Modelagem proposta](#2-modelagem-proposta)
3. [Aspectos metodológicos](#3-aspectos-metodológicos)
4. [Busca semântica calibrável](#4-busca-semântica-calibrável)
5. [Arquitetura técnica](#5-arquitetura-técnica)
6. [Bootstrap local](#6-bootstrap-local)
7. [Comandos úteis](#7-comandos-úteis)
8. [Roadmap e estado atual](#8-roadmap-e-estado-atual)
9. [Documentação relacionada](#9-documentação-relacionada)
10. [Como citar](#10-como-citar)
11. [Autoria, contato e licença](#11-autoria-contato-e-licença)

---

## 1. Contexto e motivação — de planilha a plataforma

A pesquisa em Análise Cognitiva no PPGDC vinha sendo organizada em um
pipeline **Google Forms → Sheets → Sites**, acumulando **1.443 registros**
ao longo de várias coortes de analistas. A inspeção desse acervo
(documentada em [docs/migracao/analise_legado.md](docs/migracao/analise_legado.md)
e [docs/migracao/auditoria_qualidade.md](docs/migracao/auditoria_qualidade.md))
revelou que o problema não era cosmético, mas **metodológico**:

- **Anos inválidos** (`21`, `218`, `2921` em vez de anos de quatro dígitos),
  resultantes da ausência de validação no formulário.
- **Capitalização não normalizada** de nomes de analistas (`GENIVALDO` ao
  lado de `Genivaldo`), gerando duplicatas funcionais.
- **Campos S/N com seis grafias diferentes** ("S", "N", "Sim", "Não",
  "1", "0") sem normalização possível em planilha.
- **Ausência ambígua**: vazio, "-" e "Não" misturados, sem distinção
  entre não-preenchimento e ausência intencional.
- **DOI mal formatado** ("DOI: 10.xxxx") e **links de acesso faltantes**
  em parcela significativa dos registros.
- **Variantes de base de consulta** ("scopus" / "SCOPUS" / "Scopus") e
  **variantes de termos epistemológicos** ("Empirismo" / "empirismo" /
  "Empírica" / "empirista") tratadas como entradas distintas.

Mais do que limpeza de dados, esses sintomas evidenciaram que a planilha
**não suporta a metodologia que a AnCo exige**:

- não existe revisão por pares;
- não há histórico de versões consultável;
- não há integridade referencial entre artigo, analista e termo do
  vocabulário;
- não há busca facetada nem URL estável para citação;
- divergências interpretativas entre analistas viram conflitos de edição
  em vez de ficarem preservadas como dado de pesquisa.

A AnCo (plataforma) é a resposta a esse diagnóstico. A migração dos
1.443 registros é tratada como **idempotente** e auditável (script
`manage.py migrate_legacy`), preservando o legado pré-validado em paralelo
ao acervo novo.

---

## 2. Modelagem proposta

A modelagem foi construída para tornar **explícito** no esquema do banco
o que era implícito (e frequentemente perdido) na planilha. Detalhes em
[apps/acervo/models.py](apps/acervo/models.py),
[apps/core/models.py](apps/core/models.py) e
[apps/vocabulario/models.py](apps/vocabulario/models.py).

### 2.1. Entidades

```
       ┌──────────┐   N    ┌──────────┐   N    ┌──────────┐
       │   User   │────────│  Análise │────────│  Revisão │
       └──────────┘        └──────────┘        └──────────┘
                                │ N
                                │
                                │ 1
                           ┌──────────┐    N    ┌────────────────┐
                           │  Artigo  │─────────│  SnapshotLink  │
                           └──────────┘         └────────────────┘
                                │ M
                                │
                                │ 1
                           ┌────────────────────┐
                           │ TermoVocabulario   │
                           │ (epistemologia,    │
                           │  teoria, base…)    │
                           └────────────────────┘
```

- **`User`** ([apps/core/models.py](apps/core/models.py)) — papéis
  `leitor`, `analista`, `curador`; vínculo institucional, ORCID,
  `aceita_revisoes`, `limite_revisoes_simultaneas`.
- **`Artigo`** ([apps/acervo/models.py](apps/acervo/models.py)) —
  referência bibliográfica (a plataforma nunca hospeda a obra). Identificação
  em três níveis: **DOI** → **ISBN** → **identificador interno
  determinístico** (`legacy:<hash16>` derivado de título + ano + periódico).
  Cada nível tem `UniqueConstraint`, fechando a porta para entradas duplicadas.
- **`Análise`** — avaliação estruturada de um Artigo segundo a grade AnCo:
  presença do termo (em título, resumo, palavras-chave, referências, corpo),
  pertinência, definição extraída, objeto, objetivo, foco, metodologia,
  epistemologia (M2M), teoria (M2M), referenciais, resultados, contexto de
  produção. Constraint `(artigo, analista)` garante uma análise por par,
  permitindo que **múltiplas análises do mesmo artigo coexistam quando
  feitas por analistas distintos**.
- **`Resenha crítica`** — campo opcional `resenha_critica` na Análise.
  Sua presença muda o fluxo de revisão (ver §3.3).
- **`Revisão`** — parecer estruturado (`aprovar` / `ajustes` / `rejeitar`),
  com tipo `estrutural` (autoria visível, prazo 14d) ou `cega` (autoria
  mascarada, prazo 21d) e comentários ancorados por campo da análise.
- **`Vocabulario` / `TermoVocabulario`** — listas canônicas para
  epistemologia, teoria, base de consulta, etc. Cada termo carrega
  `sinonimos` (ArrayField) que mapeia variantes ortográficas para o
  termo canônico; `TermoVocabulario.buscar_canonico()` faz lookup
  case-insensitive em nome e sinônimos.
- **`SnapshotLink`** — captura no Internet Archive vinculada ao artigo,
  para preservação contra link rot.

### 2.2. Auditoria e histórico

Todas as alterações de Análise são versionadas via `django-simple-history`,
com middleware capturando autoria. O histórico exclui apenas campos
derivados (embeddings) — o que era texto livre na planilha vira um
trilha de mudanças consultável no admin e parcialmente exposta no acervo
público.

---

## 3. Aspectos metodológicos

### 3.1. Colaboração entre analistas e papéis

A plataforma trata a pesquisa como **prática coletiva**, não como
preenchimento individual de formulário:

- **Cadastro institucional**: login via Google OAuth filtrado por
  domínios institucionais (`ALLOWED_INSTITUTIONAL_DOMAINS` configurável).
  Usuário entra como `leitor` e solicita promoção a `analista` via fluxo
  `SolicitacaoCadastro`; curador aprova pelo admin.
- **Múltiplas análises do mesmo artigo** são esperadas: dois analistas
  podem ler o mesmo artigo com lentes epistemológicas distintas, e a
  plataforma **preserva ambas as leituras** como evidência de pluralidade
  interpretativa, não como conflito.
- **Sorteio automático de revisores**
  ([apps/acervo/sorteio.py](apps/acervo/sorteio.py)) considera disponibilidade
  (`aceita_revisoes`), carga atual (`limite_revisoes_simultaneas`),
  exclui o autor da análise e exclui qualquer analista que tenha analisado
  o mesmo artigo (preserva independência de avaliação). Quando faltam
  revisores elegíveis, a análise entra em fila de espera visível para
  curadores em vez de ser submetida com revisão parcial.

### 3.2. Inserção facilitada e prevenção de duplicidade

Reduzir o atrito de inserção é parte da estratégia de qualidade — quanto
menos digitação manual, menos pontos de divergência entram no acervo.

- **Lookup automático no cadastro**: o analista digita um DOI, ISBN ou
  termo, e a interface (HTMX em
  [templates/acervo/cadastrar_artigo.html](templates/acervo/cadastrar_artigo.html))
  consulta em tempo real o Crossref
  ([apps/acervo/services/crossref.py](apps/acervo/services/crossref.py),
  cache 24h) ou o OpenLibrary
  ([apps/acervo/services/isbn.py](apps/acervo/services/isbn.py),
  cache 30d). Os metadados retornados (título, autores, periódico, ano,
  volume, página, resumo) preenchem o preview; o analista revisa e
  confirma. Quando um identificador já existe na base, a interface
  **leva o analista para a análise existente** em vez de criar duplicata.
- **Detecção de duplicidade em três níveis**: DOI → ISBN → identificador
  determinístico (hash de título+ano+periódico). Substitui matching
  textual frágil por chaves estáveis. O migrador legado usa
  `update_or_create` sobre essa chave, garantindo idempotência —
  reprocessar a importação não cria duplicatas.
- **Validação de link de acesso**:
  [apps/acervo/services/links.py](apps/acervo/services/links.py) faz
  HEAD request com fallback GET (publishers que bloqueiam HEAD) e
  guarda anti-SSRF (rejeita IPs privados/loopback). O status
  `ok | quebrado | redireciona | nao_verificado` é persistido no Artigo
  e visível no acervo. Cron semanal re-verifica artigos publicados.
- **Snapshot Wayback opcional**: ao salvar, o analista pode disparar
  captura no Internet Archive; o `SnapshotLink` resultante é exibido
  como fallback de acesso quando o link primário cai.
- **Vocabulário controlado com sinônimos**: o formulário oferece apenas
  termos `ativo=True` do vocabulário. Variantes da planilha legada foram
  importadas como `ativo=False` (visíveis para curadoria, ocultas no
  cadastro novo). Isso impede a reintrodução de "Empirismo / empirismo /
  Empírica" como entradas distintas.

### 3.3. Resenha crítica peer-reviewed

A resenha crítica é o **componente autoral original** da Análise — a
leitura interpretativa do analista sobre o artigo, distinta da
catalogação estrutural. Sua presença muda o fluxo de revisão:

- **Sem resenha**: 2 revisões `estrutural` (autoria visível, prazo 14
  dias). Análise é publicada se ambas retornam `aprovar`.
- **Com resenha**: 2 revisões `estrutural` + **2 revisões `cega`
  adicionais** (autoria mascarada, prazo 21 dias). Análise é publicada
  apenas se todas as 4 retornam `aprovar`.

Detalhes operacionais:

- **Mascaramento de autoria** na revisão cega: `nome_exibicao`,
  `username` e timestamps suficientes para reidentificação são
  substituídos por "Autor" na interface do revisor cego e em comentários
  anteriores. Testes garantem que nada da identidade vaza
  ([apps/acervo/tests/](apps/acervo/tests/)).
- **Lógica de transição** em
  [apps/acervo/aprovacao.py](apps/acervo/aprovacao.py): qualquer parecer
  `rejeitar` ou `ajustes` retorna a análise para `rascunho` com os
  comentários ancorados por campo, permitindo que o analista revise
  pontualmente. Apenas a unanimidade de `aprovar` move para `publicada`.
- **Re-sorteio automático**: tarefa diária
  ([apps/acervo/tasks.py](apps/acervo/tasks.py)) substitui revisores que
  não concluíram dentro do prazo, sem que o autor da análise precise
  intervir.
- **Selo no acervo público**: análises com resenha crítica aprovada
  exibem o selo "Resenha crítica peer-reviewed" em destaque, marcando a
  diferença entre catalogação estrutural e leitura crítica.

---

## 4. Busca semântica calibrável

A Fase 8 introduziu busca por similaridade semântica como **recurso de
acesso à informação**. A discussão metodológica que sustenta o artigo
distingue duas camadas: o que está implementado e a proposta de
**calibração ativa** pelos pesquisadores.

### 4.1. O que está implementado

Ver [apps/busca_semantica/](apps/busca_semantica/) e
[docs/relatorios/fase-8.md](docs/relatorios/fase-8.md).

- **Embeddings vetoriais** com extensão `pgvector` no PostgreSQL 16.
  Três campos `VectorField(384)` em
  [apps/acervo/models.py](apps/acervo/models.py):
  - `Artigo.embedding` — título + resumo + palavras-chave;
  - `Analise.embedding` — campos estruturais (objeto + objetivo + foco
    + metodologia + resultados + aspectos relevantes + definição
    extraída + referenciais);
  - `Analise.embedding_resenha` — apenas a resenha crítica, isolada do
    bloco estrutural.
- **Serviço de embeddings local** em container próprio
  ([infra/embeddings/](infra/embeddings/)) — FastAPI + sentence-transformers
  com modelo `paraphrase-multilingual-MiniLM-L12-v2`. Sem API externa,
  sem custo recorrente, sem dependência da disponibilidade de serviço de
  terceiros.
- **Geração assíncrona** via signals + django-q2
  ([apps/busca_semantica/tasks.py](apps/busca_semantica/tasks.py)),
  com retry/backoff e fail-safe (embedding `NULL` em falha, sem bloquear
  publicação da análise). Comando `manage.py reindexar_embeddings`
  popula o acervo já existente em lotes.
- **Toggle explícito** na busca em `/acervo/`: o pesquisador escolhe
  entre `?modo=textual` (FTS Postgres com `unaccent` e seis facetas) e
  `?modo=semantico` (pgvector). **Não há hibridização opaca** — o usuário
  sempre sabe o que está consultando.
- **Indicador de similaridade 0–100%** em cada card de resultado
  semântico, com gradação visual (verde / âmbar / cinza por faixa).
  Limite de 50 resultados, com aviso explicativo de que o ranking decai
  rapidamente.
- **Degradação graciosa**: se o serviço de embeddings está offline, a
  interface exibe aviso e cai para busca textual sem erro de página.

### 4.2. Proposta de calibração ativa pelos pesquisadores

> Esta seção descreve uma extensão metodológica **proposta para o
> artigo do II Congresso de Difusão do Conhecimento**. Parte está
> implementada (vocabulário controlado), parte é roadmap a ser defendido
> e implementado em fase subsequente.

A busca semântica em catálogos científicos pequenos sofre de um
problema conhecido: o espaço vetorial é dominado por características
genéricas do português acadêmico, e a relevância para o domínio
específico (Análise Cognitiva) emerge devagar. Em vez de aceitar isso
como ruído, a plataforma propõe **transformar o pesquisador em
calibrador do sistema** por três mecanismos complementares:

1. **Feedback de relevância por consulta** *(roadmap)*. Ao lado de cada
   resultado semântico, um par de botões `relevante` / `irrelevante`
   coleta sinal por usuário e por consulta. O sinal **não altera o
   ranking em tempo real** (preserva reprodutibilidade da busca para
   citação), mas alimenta um relatório periódico de qualidade do espaço
   vetorial usado para decidir re-embedding e curadoria de vocabulário.

2. **Limiar de similaridade ajustável** *(roadmap)*. Slider
   `min_similaridade` exposto na UI (default 0.6), configurável por
   sessão. O pesquisador estreita ou alarga o conjunto retornado
   conforme o tipo de pergunta — revisão de literatura ampla pede
   threshold baixo; busca dirigida por um conceito específico pede
   threshold alto. Calibração local, sem efeito sobre outros usuários.

3. **Curadoria do vocabulário controlado como reforço semântico**
   *(parcialmente implementado)*. O texto que entra no embedding já
   inclui termos de epistemologia e teoria. À medida que curadores
   fundem sinônimos e refinam termos canônicos em
   [apps/vocabulario/models.py](apps/vocabulario/models.py), o
   reindexador propaga esse refinamento para os embeddings. A calibração
   do vocabulário melhora **simultaneamente** a busca facetada (textual)
   e a busca semântica — duas frentes de qualidade, um único trabalho de
   curadoria.

A combinação dos três mecanismos posiciona a busca semântica como
**objeto de pesquisa** dentro da própria plataforma, não como caixa-preta
estatística — coerente com a metodologia AnCo de tornar explícitas as
escolhas interpretativas.

### 4.3. O que a busca semântica deliberadamente não faz

Conforme [docs/ESPECIFICACAO.md §6.2.1](docs/ESPECIFICACAO.md), a
plataforma **rejeita** os seguintes usos de embeddings:

- pré-preenchimento automático de campos da análise;
- detecção automática de pertinência;
- sugestão automática de revisores;
- geração assistida de resenhas críticas.

A justificativa é metodológica, não técnica: pré-preencher uma análise
com o que o modelo "acha" que outros analistas escreveram para artigos
similares contamina o ato analítico. Sugerir revisores via similaridade
quebra a aleatoriedade do sorteio. Gerar resenhas dissolve a autoria que
o peer-review existe para proteger. Busca semântica é **acesso à
informação**, não **produção de análise**.

---

## 5. Arquitetura técnica

| Camada | Tecnologia | Versão |
|---|---|---|
| Linguagem | Python | 3.12 |
| Framework web | Django | 5.x |
| Banco | PostgreSQL + pgvector | 16 |
| Cache / fila | Redis | 7 |
| Tasks assíncronas | django-q2 | ≥ 1.7 |
| Auditoria | django-simple-history | ≥ 3.7 |
| Auth | django-allauth + Google OAuth | ≥ 65 |
| Embeddings | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) | 384-dim |
| Frontend | Tailwind CSS + HTMX + Alpine.js | — |
| Servidor WSGI | Gunicorn | ≥ 22 |
| Reverse proxy / TLS | Caddy | 2 (Let's Encrypt automático) |
| Containerização | Docker Compose | v2 |
| Lint / format | ruff | ≥ 0.5 |
| Testes | pytest + pytest-django + pytest-cov | cobertura mínima 70% |
| Observabilidade | Logs JSON + Sentry SDK (opcional) | — |
| Segurança | django-csp, django-ratelimit, HSTS, anti-SSRF | — |

Detalhes em [pyproject.toml](pyproject.toml) e
[infra/docker-compose.yml](infra/docker-compose.yml).

**Frontend deliberadamente leve**: a interatividade que a planilha não
oferecia (lookup ao vivo, auto-save de 30s, busca facetada incremental)
é resolvida com HTMX no servidor + Alpine.js para estado local —
**sem SPA**. Consequência: páginas têm URL estável e citável desde o
primeiro carregamento, e o servidor permanece como fonte única da
verdade.

**Cinco serviços** sobem com `docker compose`: `web` (Django + Gunicorn),
`worker` (django-q2 qcluster), `db` (Postgres + pgvector), `cache`
(Redis), `embeddings` (FastAPI + sentence-transformers, profile
opcional). Em produção, `caddy` adiciona TLS e serve `/static/`
diretamente.

---

## 6. Bootstrap local

Pré-requisitos: **Docker 24+**, **Docker Compose v2+**, **Git**.

```bash
# 1. Copiar variáveis de ambiente
cp .env.example .env
# (edite .env e gere uma DJANGO_SECRET_KEY com:
#  python -c "import secrets; print(secrets.token_urlsafe(50))")

# 2. Subir os containers (web + db + cache)
docker compose -f infra/docker-compose.yml up -d

# 3. Aplicar migrações (inclui CREATE EXTENSION vector)
docker compose -f infra/docker-compose.yml exec web python manage.py migrate

# 4. Criar superusuário (curador inicial)
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser

# 5. Acessar
#   App:    http://localhost:8000/
#   Admin:  http://localhost:8000/admin/
#   Health: http://localhost:8000/healthz
```

**Subir o serviço de embeddings** (Fase 8) é opcional em desenvolvimento:

```bash
docker compose -f infra/docker-compose.yml --profile embeddings up -d
```

Sem o serviço, a busca em `/acervo/?modo=semantico` exibe aviso e
degrada para textual.

---

## 7. Comandos úteis

```bash
# Testes e qualidade
docker compose -f infra/docker-compose.yml exec web pytest
docker compose -f infra/docker-compose.yml exec web pytest --cov
docker compose -f infra/docker-compose.yml exec web ruff check .
docker compose -f infra/docker-compose.yml exec web ruff format .

# Shell Django e logs
docker compose -f infra/docker-compose.yml exec web python manage.py shell
docker compose -f infra/docker-compose.yml logs -f web

# Migração do legado (idempotente)
docker compose -f infra/docker-compose.yml exec web \
    python manage.py migrate_legacy --dry-run
docker compose -f infra/docker-compose.yml exec web \
    python manage.py migrate_legacy

# Embeddings (Fase 8)
docker compose -f infra/docker-compose.yml exec web \
    python manage.py reindexar_embeddings           # apenas faltantes
docker compose -f infra/docker-compose.yml exec web \
    python manage.py reindexar_embeddings --tudo    # forçar todos

# Cron de prazos e verificação de links
docker compose -f infra/docker-compose.yml exec web \
    python manage.py setup_q_schedules
```

Lista completa em [CLAUDE.md §11](CLAUDE.md).

---

## 8. Roadmap e estado atual

| # | Fase | Status | Relatório |
|---|------|--------|-----------|
| 0 | Fundação (Django + Docker + CI) | concluída | [fase-0.md](docs/relatorios/fase-0.md) |
| 1 | Núcleo de dados, admin e migrador legado | concluída | [fase-1.md](docs/relatorios/fase-1.md) |
| 2 | Autenticação, OAuth Google e cadastro | concluída | [fase-2.md](docs/relatorios/fase-2.md) |
| 3 | Criação e edição de análises | concluída | [fase-3.md](docs/relatorios/fase-3.md) |
| 4 | Revisão por pares dupla (estrutural + cega) | concluída | [fase-4.md](docs/relatorios/fase-4.md) |
| 5 | Acervo público (busca facetada, citação) | concluída | [fase-5.md](docs/relatorios/fase-5.md) |
| 6 | Saúde de links, dashboard e JSON-LD | concluída | [fase-6.md](docs/relatorios/fase-6.md) |
| 7 | Polimento, segurança e produção | concluída | [fase-7.md](docs/relatorios/fase-7.md) |
| 8 | Busca semântica (pgvector + embeddings) | concluída | [fase-8.md](docs/relatorios/fase-8.md) |
| — | Frente UX analista + lookup Crossref/ISBN | concluída | [feat-analista-ux-crossref.md](docs/relatorios/feat-analista-ux-crossref.md) |
| — | Calibração ativa da busca semântica | proposta | (a defender no artigo) |

Status vivo do roadmap em [docs/ROADMAP.md](docs/ROADMAP.md). Pendências
não-bloqueantes acumuladas (DNS, credenciais OAuth, fusão de analistas
legado) também listadas lá.

---

## 9. Documentação relacionada

- [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md) — contrato técnico
  canônico (v2.2). Em conflito com este README, a especificação
  prevalece para decisões de produto.
- [docs/tutorial_base_anco.md](docs/tutorial_base_anco.md) —
  fundamentação conceitual da Análise Cognitiva.
- [docs/especificacao_frontend.md](docs/especificacao_frontend.md) —
  design do frontend (componentes, tokens, padrões HTMX/Alpine).
- [docs/migracao/analise_legado.md](docs/migracao/analise_legado.md) e
  [docs/migracao/auditoria_qualidade.md](docs/migracao/auditoria_qualidade.md)
  — análise quantitativa do acervo legado.
- [docs/DEPLOY.md](docs/DEPLOY.md) e [docs/RESTORE.md](docs/RESTORE.md)
  — operação e recuperação de backup.
- [docs/relatorios/](docs/relatorios/) — relatórios de fim de fase, com
  decisões, desvios e dívida técnica registrados.
- [CLAUDE.md](CLAUDE.md) — convenções operacionais de desenvolvimento.

---

## 10. Como citar

Esta plataforma é objeto de comunicação científica em curso. A entrada
abaixo do artigo será atualizada após a publicação dos anais.

```bibtex
@inproceedings{vicente_anco_2026,
  author    = {Vicente, Paulo and {Grupo de Pesquisa do PPGDC}},
  title     = {De planilha a plataforma: modelagem colaborativa,
               revisão por pares e busca semântica calibrável para
               análise cognitiva da literatura científica},
  booktitle = {Anais do II Congresso de Difusão do Conhecimento},
  year      = {2026},
  note      = {No prelo}
}

@software{anco_plataforma_2026,
  author  = {Vicente, Paulo and {Grupo de Pesquisa do PPGDC}},
  title   = {{AnCo} --- Plataforma de Análise Cognitiva},
  year    = {2026},
  url     = {https://anco.paulovicente.pro.br/},
  license = {CC-BY-NC-4.0 (conteúdo); a definir (código)}
}
```

Análises individuais publicadas no acervo possuem URL estável e
citações em ABNT 6023:2018 e APA 7ª edição geradas automaticamente
([apps/publico/services.py](apps/publico/services.py)).

---

## 11. Autoria, contato e licença

**Autor principal**

- Paulo Vicente — [paulovicente.ifba@gmail.com](mailto:paulovicente.ifba@gmail.com)

**Grupo de pesquisa — PPGDC**

- Linha de pesquisa: `{{LINHA_DE_PESQUISA}}`
- Orientação: `{{ORIENTADOR}}`
- Demais pesquisadores: `{{DEMAIS_PESQUISADORES}}`

> Os campos entre chaves duplas serão preenchidos antes da submissão
> final do artigo.

**Licenciamento**

- **Conteúdo autoral hospedado** (análises, resenhas críticas, fichas):
  Creative Commons Atribuição-NãoComercial 4.0 (CC-BY-NC 4.0), conforme
  [§7 da especificação](docs/ESPECIFICACAO.md). Cada análise publicada
  exibe o selo no rodapé.
- **Código da plataforma**: licença open source compatível a definir
  antes do lançamento público do repositório.
- **Artigos referenciados**: a plataforma cataloga metadados e link de
  acesso, **nunca hospeda a obra**. Direitos autorais permanecem com
  os respectivos detentores.
