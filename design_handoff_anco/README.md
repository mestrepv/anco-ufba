# Handoff: Plataforma AnCo — telas públicas

## Visão geral

AnCo é um acervo digital colaborativo de análises de literatura científica
sobre o conceito de **Análise Cognitiva**, mantido pelo Programa de
Pós-Graduação em Difusão do Conhecimento (PPGDC — UFBA / UNEB / IFBA /
SENAI CIMATEC). Pesquisadores cadastrados leem artigos científicos e
produzem análises estruturadas seguindo uma grade conceitual fixa
(13 campos), opcionalmente acrescidas de uma resenha crítica autoral.
Análises aprovadas integram um acervo público citável (CC BY-NC).

Este handoff cobre as **três telas públicas** da plataforma:

1. **Vitrine** (homepage) — primeira impressão e convite ao acervo
2. **Acervo de busca** — listagem pública com filtros e busca textual / semântica
3. **Página de análise** — documento citável com URL estável

O formulário de cadastro de análise (analista logado) **não está incluso
neste handoff** — fica para uma segunda passada.

---

## Sobre os arquivos de design

Os arquivos em `mockups/` são **referências de design em HTML/React** —
protótipos mostrando aparência e comportamento pretendidos.
**Não são código de produção para copiar diretamente.**

A tarefa é **recriar estes mocks no ambiente do projeto: Django + HTMX
+ Tailwind CSS**, conforme as restrições técnicas declaradas no brief.
Isto significa:

- Templates Django (`templates/`) com herança via `{% extends %}` e
  blocos. Use `partials/` para fragmentos reutilizáveis (cards, selos,
  filtros) que o HTMX possa carregar isoladamente.
- HTMX para interações progressivas: filtros do acervo, paginação
  ("carregar mais"), troca textual ↔ semântica na busca, copiar citação,
  e auto-save no formulário (fora deste handoff). Sempre que possível,
  o backend devolve um fragmento HTML, não JSON.
- Tailwind CSS com tokens customizados (mapeados na seção **Design
  Tokens** abaixo) — não use a paleta default do Tailwind crua.
- Tipografia servida localmente: **Newsreader** (serif) e **Public
  Sans** (sans), via `@font-face` apontando para `static/fonts/`. Não
  carregar do Google Fonts em produção.

**Importante:** os mocks usam React + Babel inline porque o ambiente de
prototipação assim exige. Ignore React inteiramente na implementação;
traduza componentes JSX em parciais Django + classes Tailwind.

---

## Fidelidade

**Alta fidelidade (hi-fi).** Cores, tipografia, espaçamento e
hierarquia foram fixados deliberadamente. Reproduzir pixel-a-pixel,
respeitando os tokens listados abaixo. Microcopy também é definitiva
(em pt-BR, registro acadêmico moderno).

---

## Princípios de UX que regem todas as telas

1. **Hierarquia por escala tipográfica e peso, nunca por cor.** Cor
   semântica é reservada a status (resenha crítica, link quebrado,
   acesso aberto, vocabulário controlado). Decoração colorida é proibida.
2. **Mobile-first.** Tudo precisa funcionar em viewport de 375px. Os
   mocks foram entregues em 375px (mobile) e 1280px (desktop) lado a
   lado. Tablet (768–1024px) é interpolação responsiva.
3. **Alvos de toque ≥ 44 px** no mobile.
4. **Contraste WCAG AA** mínimo. Os tokens já passam.
5. **Campos vazios são ocultados, não preenchidos com placeholder.**
   Não exibir `—`, "não preenchido" nem labels desacompanhadas. Apenas
   o que tem conteúdo aparece.
6. **Sem emojis, sem gradientes, sem sombras coloridas, sem ícones
   ornamentais.** Ícones SVG inline, traço de 1.3–1.5 px.
7. **Auto-save (no formulário) silencioso e visível** — indicador
   discreto no canto, atualizado periodicamente. Nunca interromper o
   fluxo com modal ou toast.
8. **Conteúdo é prosa intelectual.** Leitura precisa ser prazerosa:
   `text-wrap: pretty`, line-height generoso, max-width 720px na coluna
   de leitura.

---

## Personalidade visual

Editorial moderno acadêmico — referências citadas pelo cliente:
*The Atlantic*, *Stratechery*, *Rest of World*. **Não** é "site
institucional brasileiro" nem "produto SaaS". Tipografia expressiva
(serifa Newsreader humanista para títulos e prosa, sans Public Sans
para UI), paleta neutra warm gray (não cool gray), espaço em branco
generoso, sem decoração ornamental.

---

## Design Tokens

### Cores (Tailwind config)

```js
// tailwind.config.js — em theme.extend.colors
{
  paper:        '#FBF9F4',  // fundo principal (creme quente)
  'paper-2':    '#F5F1E8',  // fundo secundário, faixas alternadas
  'paper-3':    '#EDE7DA',  // bordas espessas, divisores fortes
  rule:         '#E5DFCF',  // hairline padrão
  'rule-strong':'#D4CCB8',  // hairline forte (separar seções)

  ink:          '#1A1816',  // texto primário, botões sólidos
  'ink-2':      '#3A352E',  // texto de prosa
  'ink-3':      '#6B655B',  // texto secundário, metadados
  'ink-4':      '#948D80',  // texto desativado, datas

  // Semânticas — APENAS para status, nunca decorativas
  gold:         '#B8862C',  // CTA primário, links
  'gold-deep':  '#8C6520',  // links hover, eyebrow de resenha
  'review-bg':  '#FBF7E8',  // fundo do callout de resenha crítica
  'review-rule':'#E8DCA8',  // borda do callout de resenha
  danger:       '#A03A2A',  // selo "link quebrado"
  ok:           '#4A6B3A',  // selo "acesso aberto"
  info:         '#3A5A7A',  // selo "múltiplas análises"
}
```

### Tipografia

| Estilo       | Família       | Tamanho mobile | Tamanho desktop | Peso | Line-height | Tracking  |
|--------------|---------------|----------------|------------------|------|-------------|-----------|
| Display      | Newsreader    | 36 px          | 48–64 px         | 400  | 1.0–1.05    | -0.022em  |
| H1           | Newsreader    | 26–28 px       | 32–48 px         | 400  | 1.08–1.15   | -0.018em  |
| H2           | Newsreader    | 22 px          | 30–32 px         | 400/500 | 1.15     | -0.012em  |
| H3 (cards)   | Newsreader    | 17 px          | 19–20 px         | 500  | 1.25        | -0.005em  |
| Prosa        | Newsreader    | 16 px          | 17–19 px         | 400  | 1.55–1.6    | 0         |
| Body         | Public Sans   | 14 px          | 15 px            | 400  | 1.5         | 0         |
| Small        | Public Sans   | 12 px          | 13 px            | 400  | 1.45        | 0         |
| Meta         | Public Sans   | 11 px          | 12 px            | 400  | 1.4         | 0         |
| **Eyebrow**  | Public Sans   | 11 px          | 11 px            | 600  | 1.0         | **+0.14em**, **UPPERCASE** |
| Mono         | JetBrains Mono| 11–12 px       | 11–12 px         | 400  | 1.4         | 0         |

`text-wrap: pretty` em todos os títulos e prosa.

### Espaçamento

Sistema de 4 px. Padrões observados nos mocks:

- Seção mobile: padding `28px 20px` a `32px 20px`
- Seção desktop: padding `64px 56px` a `88px 56px`
- Hairlines entre items: `padding-block: 16–24px`, borda `1px solid var(--rule)`
- Container de leitura desktop: `max-width: 720px`
- Container do canvas total desktop: `max-width: 1180px`, gap entre coluna e sidebar = 80 px

### Bordas

- Border-radius: **2px** em botões e inputs (acadêmico, não rounded-lg).
- Chips de vocabulário controlado: `border-radius: 999px` (única exceção).
- Selos de status: `border-radius: 2px`.

### Sombras

**Não usar.** Hierarquia é por linha hairline + cor de fundo (`paper`,
`paper-2`).

---

## Componentes (parciais Django sugeridos)

### `partials/_wordmark.html`

Logotipo `An` (regular) + `Co` (italic) + `.` (em dourado `#B8862C`).
Newsreader, peso 500, letter-spacing -0.01em.

### `partials/_nav_desktop.html` / `_nav_mobile.html`

- Desktop: padding `20px 56px`, borda inferior `1px solid var(--rule)`,
  wordmark à esquerda, links de nav (Acervo · Sobre · Metodologia ·
  Equipe — peso 600 quando ativo, com `border-bottom: 1px solid var(--ink)`),
  CTAs "Buscar" (ghost) e "Entrar" (secondary outline) à direita.
- Mobile: padding `14px 20px`, wordmark + ícones busca/menu (40×40).

### `partials/_selo.html`

```django
{# uso: {% include "partials/_selo.html" with kind="resenha" %} #}
{# kinds: resenha · aberto · quebrado · historico · multi #}
```

Renderiza um chip com `border: 1px solid currentColor`, padding
`4px 8px`, radius 2px, font Public Sans 11px peso 500, **UPPERCASE**,
letter-spacing 0.04em. Pares cor-fundo:

- `resenha` → `text-gold-deep bg-review-bg border-review-rule`, label "resenha crítica"
- `aberto`  → `text-ok bg-ok/[0.06] border-ok/30`, label "acesso aberto"
- `quebrado`→ `text-danger bg-danger/[0.06] border-danger/30`, label "link quebrado"
- `historico` → `text-ink-3 bg-paper-2 border-rule-strong`, label "acervo histórico"
- `multi`   → `text-info bg-info/[0.06] border-info/30`, label "múltiplas análises"

### `partials/_chip.html`

Vocabulário controlado (epistemologias, teorias). `bg-paper-2`,
`border: 1px solid var(--rule)`, padding `4px 10px`, radius pílula,
font Public Sans 12px ink-2.

### `partials/_btn.html`

Variantes (`btn-primary`, `btn-secondary`, `btn-ghost`, `btn-sm`):
ver `mockups/styles.css` linhas 113–148 para valores exatos. Min-height
44 px, radius 2 px, padding `12px 18px` (sm: `8px 12px`).

### `partials/_footer.html`

Borda superior `1px solid var(--rule)`, fundo `paper-2`. Quatro colunas
desktop (Acervo · Plataforma · Institucional + brand block 2-cols),
collapse em uma coluna mobile. Texto Public Sans 12 px, ink-3.

---

## Tela 1 · Vitrine (`templates/vitrine.html`)

### Propósito
Primeira impressão para quem chega na URL. Comunica o que a plataforma
é e convida a explorar o acervo ou contribuir.

### Estrutura

1. **Nav** (parcial)
2. **Hero** — duas colunas no desktop (1.4fr / 1fr), uma no mobile
   - Coluna 1: eyebrow "Acervo digital · Difusão do conhecimento",
     H1 display "O que a literatura científica diz sobre *Análise
     Cognitiva*, organizado por quem a pratica." (com *italic* só na
     palavra "Análise Cognitiva"), parágrafo de prosa ~75 palavras.
   - Coluna 2: dois CTAs (`btn-primary` "Explorar o acervo →" e
     `btn-secondary` "Entrar para contribuir") + nota fina em `t-small`
     sobre quem pode contribuir.
3. **Métricas** — grid de 4 colunas (2×2 mobile), borda hairline em
   cima e embaixo. Cada célula: número Newsreader 44 px (32 mobile) +
   label Public Sans 13 px ink-3. Valores exatos:
   - **83** análises catalogadas
   - **24** pesquisadores contribuintes
   - **6** bases bibliográficas cobertas
   - **2008–25** amplitude de anos das obras
4. **Lista de recentes** — 5 análises mais recentes. No desktop, grid
   `120px 1fr 220px` (data esquerda · conteúdo · atribuição direita).
   No mobile, vertical. Cada item tem hairline inferior. Selos
   aplicáveis exibidos abaixo do título.
5. **Bloco de metodologia + como contribuir** — duas colunas no desktop,
   fundo `paper-2`, hairlines superior/inferior. Lista numerada (numerais
   em italic Newsreader, ink-4) com 4 passos do fluxo de contribuição.
6. **Footer** (parcial completo).

### Dados de exemplo (recentes)

Ver `mockups/screen-vitrine.jsx`, constante `RECENT_ANALYSES`. Use estes
como seed fixture inicial; em produção virá de `models.Analysis`.

---

## Tela 2 · Acervo de busca (`templates/acervo.html`)

### Propósito
Listagem do acervo, acessível sem login. Onde quem consulta encontra
análises por interesse temático ou bibliográfico.

### Estrutura

1. **Nav** com link "Acervo" ativo
2. **Header de busca** — duas colunas desktop (título + controles):
   - Eyebrow "Acervo público · 83 análises", H1 display "Buscar no acervo"
   - **Caixa de busca** alta (56px desktop / 48px mobile), borda 1.5px
     `var(--ink)`, ícone busca à esquerda, input, botão preto sólido
     "BUSCAR" à direita (uppercase, letter-spacing 0.04em).
   - **Toggle textual ↔ por significado** logo abaixo: pílula com fundo
     `paper-2` e borda hairline, segmento ativo com fundo `paper`.
     O modo "por significado" tem badge italic "VETORIAL" em ink-4.
3. **Faixa de filtros ativos + contagem + ordenação** — borda inferior
   espessa `var(--rule-strong)`. Chips removíveis (com `×`), formato
   `[grupo:] valor ×`. Direita: contagem ("27 resultados"), seletor
   "ordenar por relevância ▾", link "exportar CSV".
4. **Body** — duas colunas desktop (`260px 1fr`, gap 56px):
   - **Sidebar de filtros** (drawer no mobile, acessado por botão
     "Filtros" com badge contendo número ativo). Grupos:
     - **Ano de publicação** (slider de intervalo, 2018–2025)
     - **Base bibliográfica** (checkboxes, com contagens por base)
     - **Área do conhecimento** (checkboxes)
     - **Epistemologia** (checkboxes, vocabulário controlado)
     - **Teoria de referência** (checkboxes, vocabulário controlado)
     - **Características da análise** (collapsible — pertinência,
       define o conceito, tem resenha)
     - **Acesso & estado** (collapsible — aberto/pago, link ok/quebrado,
       publicada/histórico)
   - **Lista de resultados**, grid `1fr 200px`. Cada resultado:
     - Linha de selos (acima do título)
     - Título Newsreader 19 px peso 500
     - Autores · *periódico itálico*, ano · base
     - Snippet de prosa de 1–2 linhas
     - Coluna direita: percentual de similaridade (Newsreader 22 px),
       label "similaridade" (visível só em modo semântico), atribuição
       "analisado por [nome]" + data.
5. **Paginação** — texto "mostrando 1–8 de 27" + numerados (1 ativo
   sólido preto, demais com borda).

### HTMX endpoints sugeridos

- `GET /acervo/?q=...&semantic=1&base=Scopus&year_min=2018` →
  retorna `partials/_results_list.html` (substitui apenas a lista
  via `hx-target="#results"` e `hx-swap="outerHTML"`)
- `GET /acervo/load-more/?cursor=...` → fragmento de N resultados
  adicionais, append
- `POST /acervo/filter/toggle/` → recalcula faixa de filtros + lista

### Dados de exemplo
Ver `mockups/screen-acervo.jsx`, constante `SEARCH_RESULTS`.

---

## Tela 3 · Página de análise (`templates/analise_detail.html`)

### Propósito
Exibição completa de uma análise, citável publicamente. **A tela mais
importante do acervo** — o "documento" propriamente dito. URL estável
no padrão `/a/<slug>` (ex.: `anco.ppgdc.org.br/a/2025-santos-quilombola`).

### Estrutura

1. **Nav** com busca habilitada
2. **Breadcrumb** — `Acervo / Educação / análise`, font 12px ink-3.
3. **Cabeçalho da análise** — máx. 900px centered no desktop:
   - Linha de selos no topo (resenha crítica, acesso aberto etc.)
   - Eyebrow `Análise de` em `gold-deep`
   - H1 display 48px Newsreader, peso 400, line-height 1.08
   - Autores (Public Sans 15px ink-2) · *periódico itálico*, vol., n., p., ano
   - DOI em mono 12px linkado
   - Botões: `btn-secondary` "Acessar obra original ↗" + `btn-ghost`
     "Snapshot Internet Archive"
4. **Bloco de resenha crítica** (quando presente — destaque editorial):
   - Fundo `var(--review-bg)` (#FBF7E8), bordas hairline `var(--review-rule)`
     superior e inferior, sem padding lateral no desktop (full-bleed).
   - Container interno max-width 700px.
   - Eyebrow "Resenha crítica" em `gold-deep`, subtítulo "revisão cega
     por dois pares" italic ink-3.
   - Texto em Newsreader 19px (17 mobile), line-height 1.6.
   - **Drop cap** na primeira letra do primeiro parágrafo: float left,
     font-size 1.5em, line-height 0.9.
5. **Body de duas colunas** (desktop, max-width 1180px):
   - **Coluna principal** (max 720px) — Grade de análise, 13 campos,
     cada um:
     - Label uppercase 11 px ink-3 letter-spacing 0.12em
     - Valor: prosa Newsreader 17px ink-2 OU chips (epistemologia /
       teoria de referência)
     - Hairline inferior `var(--rule)`
     - **Campos vazios são omitidos.** Não renderizar label.
   - **Sidebar sticky** (280px) — `Nesta página` (TOC anchors:
     Cabeçalho, Resenha crítica, Grade de análise, Como citar, Autoria
     & revisão), `Análise rápida` (definition list compacta:
     Pertinência, Define o conceito, Base bibliográfica, Tem resenha),
     URL estável em mono.
6. **Bloco de citação** — fundo `paper-2`, borda hairline. ABNT e APA
   formatadas em Newsreader 14px, com botão "copiar" pequeno em cada
   uma. **HTMX**: `hx-post="/citation/copied/"` apenas para telemetria;
   o copy real é JS via `navigator.clipboard.writeText(...)`.
7. **Rodapé de metadados** — duas colunas, hairline forte superior:
   - Autoria & revisão: Análise estrutural · Revisão estrutural (assinada,
     dois nomes) · **Revisão da resenha (cega)** com "revisor A · revisor B"
     em italic.
   - Versionamento & licença: versão atual com link para histórico,
     data de publicação, licença CC BY-NC 4.0.

### Os 13 campos da grade AnCo

```
1.  Pertinência                      (sim/não)
2.  Define o conceito                (sim/não + texto se sim)
3.  Objeto do estudo                 (texto)
4.  Objetivo declarado               (texto)
5.  Foco específico                  (texto)
6.  Metodologia                      (texto)
7.  Epistemologia                    (chips · vocab controlado)
8.  Teoria de referência             (chips · vocab controlado)
9.  Referenciais teóricos citados    (texto)
10. Resultados                       (texto)
11. Aspectos relevantes              (texto)
12. Contexto de produção             (texto)
13. Observações do analista          (texto livre opcional)
```

### Dados de exemplo
Ver `mockups/screen-analise.jsx`, constante `ANALYSIS`.

---

## Modelos Django sugeridos (esqueleto)

```python
class Work(models.Model):  # a obra analisada
    doi = models.CharField(unique=True)
    title = models.TextField()
    authors = models.TextField()  # ou M2M
    journal = models.CharField()
    volume = models.CharField()
    number = models.CharField()
    pages = models.CharField()
    year = models.IntegerField()
    bib_base = models.CharField(choices=BIB_BASES)
    open_access = models.BooleanField()
    primary_url = models.URLField()
    archive_snapshot_url = models.URLField(blank=True)
    link_status = models.CharField(choices=[("ok","ok"),("broken","broken")])
    abstract = models.TextField()

class Analysis(models.Model):
    slug = models.SlugField(unique=True)  # ex.: 2025-santos-quilombola
    work = models.ForeignKey(Work, on_delete=PROTECT)
    analyst = models.ForeignKey(User, related_name="analyses")
    # 13 campos da grade
    is_pertinent = models.BooleanField()
    defines_concept = models.BooleanField()
    concept_definition = models.TextField(blank=True)
    object_of_study = models.TextField(blank=True)
    declared_objective = models.TextField(blank=True)
    specific_focus = models.TextField(blank=True)
    methodology = models.TextField(blank=True)
    epistemology = models.ManyToManyField(Epistemology)  # vocab controlado
    theory_of_reference = models.ManyToManyField(Theory)  # vocab controlado
    theoretical_references = models.TextField(blank=True)
    results = models.TextField(blank=True)
    relevant_aspects = models.TextField(blank=True)
    production_context = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    # resenha crítica (opcional)
    review_text = models.TextField(blank=True)
    # versionamento
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True)
    is_legacy = models.BooleanField(default=False)  # acervo histórico

class Review(models.Model):
    analysis = models.ForeignKey(Analysis)
    reviewer = models.ForeignKey(User)
    kind = models.CharField(choices=[("structural","structural"),("blind","blind")])
    decision = models.CharField(choices=DECISIONS)
```

`is_pertinent`, `defines_concept`, `concept_definition`, etc. são os
gatilhos para ocultação editorial — em template, renderize cada campo
apenas se truthy.

---

## Assets

- **Fontes** (servir localmente em `static/fonts/`):
  - Newsreader (300–700, ital + roman, opsz variável) — SIL Open Font License
  - Public Sans (300–700, ital + roman) — SIL Open Font License
  - JetBrains Mono (400, 500) — SIL Open Font License
- **Ícones**: SVG inline traço 1.3–1.5 px. Conjunto usado: search,
  arrow-right, arrow-left, external-link, filter, menu, x, copy, download,
  chevron-down, link, broken-link, check, bookmark. Ver definições em
  `mockups/ui-shared.jsx`, objeto `Icon`.
- **Logo**: wordmark tipográfico apenas, sem logotipo gráfico.

---

## Arquivos neste pacote

```
design_handoff_anco/
├── README.md                       (este arquivo)
└── mockups/
    ├── AnCo — Mockups.html         (entrypoint — abrir num browser para ver)
    ├── styles.css                  (tokens canônicos + classes utilitárias)
    ├── ui-shared.jsx               (Icon, Wordmark, Nav, Footer)
    ├── screen-vitrine.jsx          (homepage — mobile + desktop)
    ├── screen-acervo.jsx           (busca pública — mobile + desktop)
    ├── screen-analise.jsx          (página de análise — mobile + desktop)
    ├── design-canvas.jsx           (apenas wrapper de visualização — ignorar)
    └── tweaks-panel.jsx            (apenas controles de prototipação — ignorar)
```

`design-canvas.jsx` e `tweaks-panel.jsx` são infraestrutura do ambiente
de mocks; **não traduzir para Django**. Para preview offline, abra
`AnCo — Mockups.html` num servidor estático local (ou direto pelo
browser, com CORS desabilitado para fontes do Google).

---

## Ordem sugerida de implementação

1. **Tokens + tipografia**: configurar `tailwind.config.js` com a paleta
   acima, adicionar `@font-face` locais, criar utilities `.t-display`,
   `.t-h1`, etc. (ou usar `@apply`).
2. **Parciais base**: `_wordmark`, `_nav_*`, `_footer`, `_selo`, `_chip`,
   `_btn`. Validar visualmente contra os mocks renderizados.
3. **Vitrine** estática (sem dados reais, hardcoded das fixtures dos mocks)
   para validar layout end-to-end.
4. **Models + admin** mínimos para Analysis + Work; popular com
   ~10 fixtures.
5. **Página de análise** ligada aos models. Esta é a tela mais
   importante — invista em chegar perto pixel-a-pixel.
6. **Acervo de busca** com filtros server-side + HTMX para troca
   de modo e paginação. Busca semântica (vetorial) pode ficar atrás de
   feature flag inicialmente — UI já está pronta.
7. **Acessibilidade**: passar AXE/Lighthouse, navegação por teclado,
   labels em todos os inputs e botões-ícone.

---

## Contato / dúvidas

Em caso de dúvida sobre tokens, espaçamento ou microcopy, **abrir o
mock correspondente** (`screen-*.jsx`) — ele contém o conteúdo real
exato. Os números no `styles.css` são a fonte canônica para dimensões.
