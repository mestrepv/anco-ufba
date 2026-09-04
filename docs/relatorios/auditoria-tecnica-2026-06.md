# Auditoria técnica da plataforma AnCo

> **Data:** 2026-06-07
> **Escopo:** repositório completo (`apps/`, `config/`, `infra/`, `docs/`, CI, dados versionados).
> **Natureza:** análise estática + leitura de configuração. Nenhuma linha de código foi alterada.
> **Método:** leitura dos documentos canônicos (CLAUDE.md, README, protocolo), métricas
> quantitativas do repositório e três varreduras dirigidas (qualidade/gambiarras,
> segurança defensiva, infra/testes/dados).

---

## 0. Veredito em uma frase

Esta **não** é uma aplicação amadora. É um projeto Django de qualidade
profissional acima da média do meio acadêmico: settings de produção endurecidos,
CI com lint+format+testes e gate de cobertura, ~510 testes, modelagem com
constraints, logging estruturado, Sentry, CSP, separação de ambientes e
documentação operacional real (DEPLOY/RESTORE/ROADMAP). Os problemas existentes
são **pontuais e corrigíveis**, não estruturais — e nenhum deles é uma "gambiarra
escondida". O maior risco concreto é de **infra/CI** (CI roda sem a extensão
pgvector que a migração exige), não de código de aplicação.

**Nível de profissionalismo: 8/10.** Sólido para o porte (acervo de pesquisa de
grupo). O que falta para 9–10 é endurecer a borda (uploads, SSRF em redirect),
fechar a lacuna CI↔produção e tornar o build reprodutível (lockfile).

---

## 1. Pontos fortes (o que está bem-feito)

### 1.1. Configuração e segurança de plataforma
- **Separação de settings** `base/dev/prod` limpa, via `django-environ`. Sem
  segredo hardcoded em código ([config/settings/base.py](config/settings/base.py)).
- **`.env` nunca foi commitado** — confirmado em `git log --all -- .env` (vazio).
  O `.gitignore` cobre `.env`, dumps, exports, caches.
- **Produção endurecida** ([config/settings/prod.py](config/settings/prod.py)):
  `SECURE_SSL_REDIRECT`, HSTS 1 ano com preload, cookies `Secure`,
  `CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`, `CSRF_TRUSTED_ORIGINS` derivado
  de `ALLOWED_HOSTS`, **CSP via django-csp**, **logging JSON estruturado** e
  **Sentry/GlitchTip** opcional. Esse conjunto é raro em projeto acadêmico.
- **Rate limiting do allauth** configurado (login/signup/e-mail).

### 1.2. Modelagem e domínio
- Integridade por **`constraints`** (UniqueConstraint/CheckConstraint), não por
  signals — exatamente o que o CLAUDE.md exige. Os signals fazem só disparo de
  tasks e captura de estado, não validação de negócio.
- Identificação de artigo em três níveis (DOI → ISBN → hash determinístico) com
  unicidade — desenho maduro para deduplicação.
- **Auditoria por linha** (django-simple-history) em Análise e Resenha.
- App de triagem **aditivo** (tabelas próprias, não toca o schema do acervo) —
  decisão arquitetural correta que isola risco.

### 1.3. Testes e CI
- **~510 funções de teste** em 51 arquivos. Os domínios críticos (acervo: ~219,
  triagem: ~170, publico: ~65) estão bem cobertos, incluindo sorteio cego, κ de
  Fleiss, duplicatas e fluxos de status.
- **CI real** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): `ruff check`
  + `ruff format --check` + `pytest --cov --cov-fail-under=70`, com serviços
  Postgres e Redis. Gate de cobertura imposto, não decorativo.

### 1.4. Disciplina de processo
- **Zero gambiarras marcadas**: a varredura por `TODO/FIXME/HACK/XXX/workaround`
  retornou essencialmente nada (os 91 "matches" de um grep amplo são falsos
  positivos — "todos", "Métodos", "provisória" em texto). Não há dívida técnica
  comentada e esquecida no código.
- **`# noqa` justificados** (19, sobretudo `F401` de registro de signals,
  `BLE001` em tasks/commands, `F403/F405` em settings) — não escondem problemas.
- Commits atômicos em Conventional Commits, documentação de fases e roadmap.

---

## 2. Pontos fracos e riscos (priorizados)

> Severidade reflete impacto × probabilidade **neste contexto** (acervo de
> pesquisa, equipe pequena, tráfego baixo, dados públicos por design).

### 🔴 ALTA — resolver antes de confiar no CI / próximo deploy

**A1. CI roda sem a extensão pgvector que a migração exige.**
A migração [apps/busca_semantica/migrations/0001_pgvector_extension.py](apps/busca_semantica/migrations/0001_pgvector_extension.py)
executa `CREATE EXTENSION IF NOT EXISTS vector;`, mas o CI usa a imagem
`postgres:16` **pura** ([.github/workflows/ci.yml:39](.github/workflows/ci.yml#L39)),
que **não inclui pgvector**. A produção usa `pgvector/pgvector:pg16`
([infra/docker-compose.yml:3](infra/docker-compose.yml#L3)). Consequência: ou o
CI está vermelho/sendo ignorado, ou os testes que exercem embeddings não rodam a
migração — em ambos os casos **o CI não está validando o caminho de produção**.
(`pg_trgm` e `unaccent` vêm no contrib do Postgres oficial, então esses estão ok;
só o `vector` falta.)
- **Ação:** trocar a imagem do CI para `pgvector/pgvector:pg16` (ou um Postgres
  com pgvector instalado). Verificar imediatamente se a suíte está de fato verde.

**A2. Build não-reprodutível (sem lockfile).**
[pyproject.toml](pyproject.toml) usa só ranges abertos (`>=`) em ~17 dependências,
sem `uv.lock`/`poetry.lock`/`requirements-lock.txt`. Dois `docker build` em datas
diferentes podem instalar versões diferentes de Django/allauth/etc. — fonte
clássica de "funcionava ontem".
- **Ação:** adotar `uv` (ou `pip-tools`) e commitar um lockfile; o Dockerfile e o
  CI passam a instalar a partir dele. Documentar em DEPLOY.md.

### 🟠 MÉDIA — endurecer a borda e a operação

**M1. SSRF: a guarda não revalida redirects.**
[apps/acervo/services/links.py:38-79](apps/acervo/services/links.py#L38-L79):
`_eh_url_publica()` resolve e rejeita IP privado **da URL original**, mas depois
`requests.head(url, allow_redirects=True)` segue redirects **sem revalidar cada
salto**. Um host público que redirecione para `http://169.254.169.254`
(metadata de nuvem) ou `http://127.0.0.1` seria seguido. Há ainda uma janela de
TOCTOU/DNS-rebinding (resolve-e-depois-conecta). Risco real, probabilidade baixa
neste deploy (sem cloud-metadata exposto), mas é o tipo de coisa que vaza.
- **Ação:** `allow_redirects=False` + seguir manualmente revalidando `_eh_url_publica`
  em cada `Location`, com limite de saltos. Considerar bloquear esquemas non-http
  no redirect.

**M2. Uploads sem validação de tipo/tamanho antes do parse.**
- Import de triagem ([apps/triagem/forms.py](apps/triagem/forms.py),
  [apps/triagem/views.py](apps/triagem/views.py)): `FileField` sem
  `FileExtensionValidator` nem limite de tamanho; o arquivo é aceito e só então
  `rispy`/`bibtexparser` tentam parsear. Sem teto de tamanho, um arquivo enorme
  vira consumo de memória/CPU.
- Foto de perfil ([apps/core/forms.py](apps/core/forms.py)): `ImageField` aberto
  com PIL antes de qualquer limite de bytes — decompression bomb possível.
- **Ação:** `FileExtensionValidator(['ris','bib','csv'])` + validador de tamanho
  (ex.: 10–20 MB) no import; limite de bytes + `Image.MAX_IMAGE_PIXELS` na foto.

**M3. Importação sem rate limit.**
`importar_view` ([apps/triagem/views.py](apps/triagem/views.py)) e os lookups
externos (Crossref/OpenLibrary) não têm `@ratelimit`. Mesmo restrito a
curador/admin, um POST repetido de arquivo grande é um vetor de DoS interno.
- **Ação:** `@ratelimit(key="user", rate="…", method=["POST"])` nos endpoints de
  upload/lookup.

**M4. Dados de produção em arquivos soltos na raiz do projeto.**
Na raiz há `backup_triagem_pre_delete.json` (9 MB), `base-anco-export-2026-06-03.json`
(1.6 MB), `prod_doi_auditoria.csv`, `prod_doi_correcoes.csv`, `dois_*.json`,
`conflitos_doi.csv`, `.coverage`. **Verificado: nenhum está rastreado no git** (o
`.gitignore` cobre os padrões), então não vazaram — mas ficam no diretório de
deploy como exportações ad-hoc de produção. Risco de backup acidental num tar, de
serem servidos por engano, e de poluir o working tree.
- **Ação:** mover para um diretório fora do repo (`var/` ou `~/exports/`) ou um
  `scratch/` ignorado; o JSON de 5.1 MB em [dados/legado/base-referencial-corrigida.json](dados/legado/base-referencial-corrigida.json)
  **está** versionado e infla o `.git` — avaliar se precisa estar no histórico.

**M5. CI verde ≠ produção saudável (extensões à parte).**
Faltam, no compose, limites de recursos (`mem_limit`/`cpus`) e healthcheck no
serviço `web` (só `depends_on`). O backup ([infra/backup/run.sh](infra/backup/run.sh))
gera dumps mas (conforme a varredura) **não faz rotação** — `/var/backups` cresce
sem poda.
- **Ação:** `deploy.resources.limits` nos serviços; healthcheck `GET /healthz` no
  `web`; `find … -mtime +N -delete` no backup; **executar um teste real de restore**
  (RESTORE.md prevê trimestral e nunca foi exercido).

### 🟡 BAIXA — higiene e robustez

**B1. Views grandes com lógica de negócio embutida.**
`apps/triagem/views.py` (1.229 linhas) não tem `services.py`; `painel_view`
(~143 linhas) e `autotriar_view` (~96) misturam montagem de contexto, permissão
e queries. O acervo já dá o bom exemplo (`apps/acervo/services/`). Não é bug —
é manutenibilidade. Refatorar **antes** de crescer mais.
- **Ação:** criar `apps/triagem/services.py` e extrair `_construir_painel_anco/_prisma`
  e a lógica de autotriagem.

**B2. Duplicação intencional triagem↔acervo (~650 linhas).**
`sorteio.py`/`aprovacao.py`/`signals.py`/`tasks.py` são ~70–95% espelhados entre
os dois apps. O CLAUDE.md documenta isso como decisão ("espelha, não generaliza").
É defensável, mas o risco prático é **corrigir um bug num lado e esquecer o outro**.
- **Ação:** manter a decisão, mas adicionar um teste de paridade ou um comentário
  cruzado `# espelha apps/acervo/sorteio.py::executar_sorteio` em cada par, para
  que a divergência seja notada.

**B3. `except Exception` largo em alguns pontos.**
17 ocorrências; a maioria com `logging.exception` (ok em tasks). Dois pontos
silenciam sem contexto suficiente: `apps/core/admin_dashboard.py` (`except: pass`
com `# noqa: BLE001`) e o lookup em `apps/acervo/views.py`. `print()` em duas
migrations de dados (0009, 0013) em vez de `self.stdout.write`.
- **Ação:** logar com contexto; trocar `print` por `self.stdout.write` nas migrations.

**B4. Migration de dados irreversível e silenciosa.**
[apps/acervo/migrations/0009_migrar_resenhas_e_limpar_revisao.py](apps/acervo/migrations/0009_migrar_resenhas_e_limpar_revisao.py)
faz `.delete()` de revisões estruturais com reverse no-op (perda permanente) e
loga via `print`. É idempotente (bom), mas irreversível sem aviso.
- **Ação:** apenas documentar a irreversibilidade no topo da migration (já aplicada;
  não reescrever histórico).

**B5. Cobertura desigual nos apps pequenos.**
`vocabulario` (~8 testes, sem teste de `buscar_canonico`/sinônimos) e
`busca_semantica` (integração testada, **qualidade não** — falta a avaliação
qualitativa que a Fase 8 previa) estão fracos. `core` (adapters/admin actions)
também é magro.
- **Ação:** testes para canonização de vocabulário e um `docs/busca_semantica/avaliacao.md`
  com 10 consultas representativas (textual × semântico).

**B6. `USER_AGENT` e domínio hardcoded.**
[apps/acervo/services/links.py:24](apps/acervo/services/links.py#L24) embute o
domínio antigo. Pequeno, mas o README já sinaliza migração de DNS para
`anco.ufba.br` — vai virar inconsistência.
- **Ação:** mover para settings/env.

---

## 3. Notas de correção sobre achados de varredura

Para evitar pânico baseado em falso positivo (importante registrar):

- **"Secrets versionados no `.env`" — FALSO.** Uma das varreduras leu o `.env`
  em disco e concluiu que estava versionado. **Não está**: `git log --all -- .env`
  é vazio; nunca foi commitado. Os segredos vivem em plaintext no `.env` do
  servidor, o que é o esperado para um deploy. **Nenhuma ação de revogação de
  emergência é necessária por causa do git.** (Boa prática geral de rotação
  periódica continua valendo, mas não há vazamento.)
- **"91 TODOs/gambiarras" — FALSO.** São casamentos espúrios de "todos/Métodos/
  provisória" em texto normal. O código está limpo de marcadores de dívida.
- **Signup aberto a qualquer Google — INTENCIONAL, não falha.** O controle de
  qualidade está no gate de promoção a analista (`SolicitacaoCadastro`), por
  design (CLAUDE.md/README). A validação de domínio institucional existe para
  outro fim e não é burlada.

---

## 4. Plano de ação recomendado

**Fazer agora (horas, destrava confiança no CI/deploy):**
1. [A1] Trocar imagem do Postgres no CI para `pgvector/pgvector:pg16` e confirmar suíte verde.
2. [A2] Gerar e commitar lockfile (`uv lock` ou `pip-compile`); instalar a partir dele no Docker/CI.
3. [M4] Tirar `*.json`/`*.csv` de produção da raiz do projeto.

**Fazer em seguida (endurecimento, ~1 dia):**
4. [M2] Validadores de extensão+tamanho nos uploads (triagem e foto).
5. [M1] Revalidar redirects no `validar_link` (anti-SSRF).
6. [M3] Rate limit nos endpoints de upload/lookup.
7. [M5] Limites de recurso + healthcheck do `web` + rotação de backup + **um restore de verdade**.

**Higiene contínua (quando tocar nas áreas):**
8. [B1] Extrair `services.py` em triagem antes de crescer mais.
9. [B5] Testes de vocabulário + avaliação documentada da busca semântica.
10. [B3/B6] Logging com contexto; mover USER_AGENT/domínio para env.

---

## 5. Métricas de referência

| Dimensão | Número |
|---|---|
| Código Python (apps + config) | ~23.000 linhas |
| Apps | 6 (core, acervo, triagem, publico, vocabulario, busca_semantica) |
| Funções de teste | ~510 em 51 arquivos |
| Migrations | acervo 13 · triagem 20 · core 4 · vocabulario 3 · publico 2 · busca_semantica 1 |
| Gate de cobertura no CI | 70% |
| Marcadores de dívida reais (TODO/FIXME/HACK) | ~0 |
| `except Exception` | 17 (maioria com logging) · `# noqa` 19 (justificados) |
| Maiores arquivos | triagem/views.py 1229 · acervo/views.py 920 · triagem/models.py 771 |

---

*Relatório gerado por análise estática. Recomenda-se, como próximo passo de maior
valor, apenas verificar o status atual do CI no GitHub Actions — ele confirma ou
refuta empiricamente o achado A1 em segundos.*
