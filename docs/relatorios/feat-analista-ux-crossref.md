# Relatório — Frente UX Analista + lookup Crossref/ISBN

**Branch**: `feat/analista-ux-crossref`
**Concluída em**: 2026-05-01
**Roadmap**: [`docs/planos/feat-analista-ux-crossref.md`](../planos/feat-analista-ux-crossref.md)

## O que foi entregue

- **Backend**:
  - `apps/acervo/services/crossref.py`: lookup DOI via Crossref com cache
    Redis 24h, normalização de prefixos (`https://doi.org/`, `doi:`), e
    limpeza de tags JATS no abstract.
  - `apps/acervo/services/isbn.py`: lookup ISBN via OpenLibrary com cache
    30 dias e validação de checksum ISBN-10 (mod 11) e ISBN-13 (mod 10).
  - `apps/acervo/services/_base.py`: dataclass `LookupResultado`
    compartilhada.
  - `apps/acervo/services/links.py`: validar_link e snapshot Wayback
    movidos do antigo `services.py`.
  - Modelo `Artigo` agora aceita ausência de DOI: campos `doi` (nullable),
    `isbn` (nullable, unique), `tipo_publicacao` (choices),
    `identificador_interno` (gerado em `save()` quando os outros estão
    vazios). Property `identificador_canonico` retorna o melhor
    disponível.
  - Migration `0004_artigo_sem_doi`: aplica os novos campos e move
    registros legacy:HASH do campo `doi` para `identificador_interno`.
    Reversível.
  - Forms divididos: `IdentificadorLookupForm` (passo 1, com detecção
    automática de tipo: DOI / ISBN-10 / ISBN-13 / URL / desconhecido /
    vazio) e `ArtigoMetadadosForm` (passo 3, campos editáveis com
    validação rigorosa). `ArtigoForm` mantido como alias temporário.
  - Nova view `lookup_identificador_view` (HTMX, GET, decorator
    `_exige_analista`). Roteia para o serviço correto, detecta artigo
    já cadastrado no acervo e oferece link para a análise existente.
  - `cadastrar_artigo_view` reescrita: GET aceita pré-preenchimento via
    querystring; POST usa `ArtigoMetadadosForm`.

- **Frontend (design editorial)**:
  - Novos tokens em `static/css/input.css` (@layer components):
    `.lookup-input`, `.field-input`, `.field-textarea`, `.field-label`,
    `.meta-card`, `.meta-row`, `.step-indicator`, `.badge`, `.badge-ok`,
    `.badge-warn`, `.badge-err`, `.spinner`.
  - 5 templates migrados de `_base.html` para `_base_publico.html` com
    tipografia editorial Newsreader / Public Sans / JetBrains Mono:
    - `cadastrar_artigo.html`: 4 passos editoriais (identificador →
      preview → form → ação) com lookup HTMX em tempo real.
    - `editar_analise.html`: stepper com indicadores numerados, cartão
      de identificação com selo de link, auto-save indicator discreto,
      passo de resenha em fundo `.review-bg`.
    - `minhas_analises.html`: tabela trocada por grid de cards via novo
      partial `_card_analise.html` reutilizável.
    - `submeter_analise.html`: confirmação com checklist visual.
    - `buscar_artigo.html` + `_busca_resultados.html`: alinhados com a
      vitrine pública.
  - Novo partial `_preview_metadados.html` retornado pelo HTMX.

- **Testes**:
  - `test_crossref_service.py` (14 cenários)
  - `test_isbn_service.py` (15 cenários)
  - `test_artigo_sem_doi.py` (10 cenários)
  - `test_forms_artigo.py` (21 cenários)
  - `test_lookup_view.py` (10 cenários)
  - `test_e2e_analista.py` (6 cenários cobrindo fluxo completo: DOI,
    ISBN, sem identificador, navegação)

## Critério de aceite (do roadmap)

- [x] M0 — Setup da branch
- [x] M1 — Lookup DOI Crossref + cache 24h
- [x] M2 — Lookup ISBN OpenLibrary + cache 30 dias
- [x] M3 — Model permite Artigo sem DOI
- [x] M4 — Forms divididos com validação
- [x] M5 — View HTMX + cadastrar_artigo reescrita
- [x] M6 — Frontend cadastrar_artigo aplica o mockup
- [x] M7 — Frontend demais telas (editar, minhas, submeter, buscar)
- [x] M8 — Tests E2E + cobertura ≥70% + relatório

## Decisões tomadas

1. **Sem cascata de APIs para resumo**: o roadmap chegou a propor
   Crossref → Semantic Scholar → OpenAlex em sequência para preencher
   abstract, mas acabamos optando por uma só API por tipo de
   identificador. Latência média cai pela metade (~850 ms → ~400 ms),
   pior caso cai 3× (15 s → 5 s), e ~50% dos artigos vão pedir o
   resumo digitado pelo analista — operação simples (Ctrl-C/Ctrl-V do
   PDF que ele já está olhando). Documentado em
   [feat-analista-ux-crossref.md §1, §2 e tabela de riscos].

2. **Sem fallback Google Books no ISBN**: mesmo princípio. OpenLibrary
   é a única fonte; ISBN não encontrado → analista preenche
   manualmente.

3. **Identificador interno determinístico**: para artigos sem DOI nem
   ISBN, geramos `legacy:<hash16>` a partir de SHA-1
   (título|ano|periódico). Mesmo padrão usado pelo migrador da Fase 1,
   mantendo idempotência. Isso permite que dois analistas cadastrando
   o mesmo artigo manualmente caiam em `update_or_create` em vez de
   duplicar.

4. **`legacy:HASH` movido de `doi` para `identificador_interno`**: a
   migration M3 move registros do legado importados na Fase 1 para o
   novo campo, liberando o campo `doi` para receber DOI canônico
   futuramente sem violar o `unique` constraint.

5. **`Artigo.save()` normaliza strings vazias para `None`**: o
   ModelForm grava strings vazias por padrão; Postgres precisa de NULL
   para múltiplos artigos sem DOI/ISBN coexistirem com `unique=True`.

6. **Tokens CSS em `@layer components`**: novos tokens convivem com o
   design system existente sem quebrar páginas que já estavam usando
   `.input`, `.btn`, `.t-h1`, etc.

## Desvios da especificação

- **Cadastro sem DOI nem ISBN**: a especificação original (`docs/especificacao/ESPECIFICACAO.md`
  §4.1) tratava DOI como obrigatório. O modelo agora aceita 3 caminhos
  (DOI, ISBN ou identificador interno) — desvio motivado pela
  auditoria do legado, que mostrou ~150 entradas (livros, capítulos,
  dissertações) sem DOI legítimo.

- **Tipo de publicação como atributo do `Artigo`**: a especificação
  cobria apenas artigos de periódico. Acrescentamos `tipo_publicacao`
  com choices (artigo, capítulo, livro, dissertação, tese, outro)
  para lidar com a diversidade real do legado.

## Dívida técnica deixada

- **`apps.acervo.forms.ArtigoForm` segue como alias** de
  `ArtigoMetadadosForm` para preservar imports antigos. Pode ser
  removido quando confirmarmos que nenhum lugar do projeto importa o
  nome antigo.
- **Tipo de publicação não é mapeado automaticamente** a partir do
  campo `type` do Crossref (journal-article, book-chapter, etc.).
  Hoje é editável pelo analista no passo 3. Mapeamento automático
  seria 1 commit pequeno.
- **Tabela `LinkQuebrado` foi adicionada à migration 0004** (proxy
  model que estava pendente de uma fase anterior, captado pelo
  `makemigrations` automaticamente). Não é parte do escopo desta
  frente mas precisa ser declarada explicitamente.
- **15 warnings ruff** em `apps/busca_semantica/` e `apps/publico/`
  (B905, I001, E402) são pré-existentes — fora do escopo desta
  frente. Sugiro um commit separado de `chore(quality): ruff check`
  varrendo o repo.
- **ISBN lookup usa só OpenLibrary** (sem Google Books como fallback).
  Cobertura para livros brasileiros é parcial — analista preenche
  manualmente quando necessário.

## Métricas

- **Commits na branch**: 8 (`refactor`/`feat`/`style`/`docs`)
- **Arquivos alterados**: 27
- **Linhas adicionadas / removidas**: +2.547 / −361
- **Cobertura `apps/acervo`**: **93%** (TOTAL 1.356 linhas, 101 missed)
- **Suite**: **361 passed, 1 xfailed, 0 failed** em ~100 s
- **`ruff check apps/acervo apps/core/views.py`**: limpo

## Pendências para o usuário

- Validar visualmente o fluxo em produção (login analista → buscar →
  cadastrar via DOI → editar → submeter): URLs disponíveis em
  `https://anco.paulovicente.pro.br/acervo-analista/` após
  `docker compose --profile prod up -d --build`.
- Decidir se o alias `ArtigoForm` deve ser removido agora (1 grep +
  rename) ou mantido como retrocompatibilidade.
- Decidir se o ISBN lookup deve ganhar Google Books como segunda
  fonte caso a cobertura de livros brasileiros se mostre fraca em uso
  real.
- Considerar varredura de `ruff` no repo todo num commit separado.
