# Especificação de Implementação — Plataforma AnCo

> **Para o desenvolvedor (Claude Code):** este documento é o roteiro de
> execução. Cada **Fase** é uma instrução autocontida — leia a fase,
> consulte os arquivos referenciados em `design_handoff_anco/`, execute,
> e só então avance. Não pule fases. Ao terminar cada fase, valide
> visualmente abrindo `design_handoff_anco/mockups/AnCo — Mockups.html`
> num browser e comparando com o que você implementou.
>
> **Stack obrigatória:** Django 5.x + HTMX + Tailwind CSS 3.x.
> Tipografia servida localmente (sem CDN do Google Fonts em produção).
> Português (pt-BR) em toda a UI.
>
> **Princípio central:** os arquivos `.jsx` em `mockups/` são
> referência visual e fonte da microcopy exata. Traduza JSX → templates
> Django; não copie HTML deles direto.

---

## Fase 0 — Preparação do ambiente

**Objetivo:** estrutura mínima do projeto Django pronta para receber o
design system.

**Tarefas:**

1. Confirmar que o projeto Django roda (`python manage.py runserver`).
2. Instalar dependências:
   - `django-htmx`
   - `django-tailwind` (ou `pytailwindcss`, conforme preferência do projeto)
   - `whitenoise` (servir estáticos em prod)
3. Configurar Tailwind (`tailwind.config.js`) com `content` apontando
   para `templates/**/*.html` e `**/*.py`.
4. Configurar `STATIC_URL`, `STATICFILES_DIRS`, `MEDIA_URL`.
5. Adicionar `htmx` ao `INSTALLED_APPS` e middleware.
6. Criar app `acervo` (ou nome equivalente) que vai conter as views.

**Critério de aceite:** servidor Django roda; `runserver` mostra "OK"
e Tailwind compila sem erros.

---

## Fase 1 — Design tokens + tipografia

**Objetivo:** o design system está disponível como classes Tailwind e
tipografia local.

**Prompt para executar:**

```
Leia design_handoff_anco/README.md, seção "Design Tokens".
Aplique todas as cores listadas em tailwind.config.js sob theme.extend.colors.
Não use a paleta default do Tailwind para nada relacionado ao AnCo.

Depois, leia design_handoff_anco/mockups/styles.css.
Converta as classes utilitárias .t-display, .t-h1, .t-h2, .t-h3,
.t-prose, .t-body, .t-small, .t-meta, .t-eyebrow para utilities Tailwind
(prefira definir em @layer components, dentro do CSS principal, usando @apply).

Baixe e instale localmente as fontes:
- Newsreader (variável, opsz 6..72, ital + roman, weights 300-700)
- Public Sans (ital + roman, weights 300-700)
- JetBrains Mono (weights 400, 500)

Coloque em static/fonts/. Crie static/css/fonts.css com @font-face apontando
para arquivos locais (use formats woff2). Adicione font-display: swap.

Configure font-family no Tailwind:
  serif: ['Newsreader', 'Georgia', 'serif']
  sans:  ['Public Sans', 'system-ui', 'sans-serif']
  mono:  ['JetBrains Mono', 'ui-monospace', 'monospace']

Faça body usar a sans por padrão, e cor ink (#1A1816) sobre fundo paper (#FBF9F4).
Adicione text-wrap: pretty global em h1, h2, h3, p, .t-prose.
```

**Critério de aceite:** uma página de teste com `<h1 class="t-display">Olá</h1>`
renderiza em Newsreader 48px sobre fundo creme `#FBF9F4`.

---

## Fase 2 — Parciais base reutilizáveis

**Objetivo:** componentes de UI prontos como includes Django.

**Prompt para executar:**

```
Leia design_handoff_anco/README.md, seção "Componentes".
Leia design_handoff_anco/mockups/ui-shared.jsx para ver o JSX de cada um.

Crie templates/partials/ com os seguintes arquivos:

1. _wordmark.html
   - Tag <span> com An (Newsreader 500) + Co (Newsreader italic 400) + . (gold)
   - Aceita parâmetro `size` (default 18)

2. _nav_desktop.html
   - Padding 20px 56px, border-bottom hairline
   - Wordmark à esquerda
   - Lista de nav: Acervo · Sobre · Metodologia · Equipe
     (peso 600 quando ativo, com border-bottom 1px var(--ink))
   - Direita: btn-ghost "Buscar" + btn-secondary "Entrar"
   - Aceita parâmetro `active` para marcar item ativo

3. _nav_mobile.html
   - Padding 14px 20px, border-bottom hairline
   - Wordmark + ícones busca/menu (40x40, traço 1.5px)

4. _footer.html
   - Border-top hairline, fundo paper-2
   - 4 colunas desktop, 1 coluna mobile
   - Microcopy exata: ver screen-vitrine.jsx, função Footer
   - Aceita parâmetro `compact` (true reduz a 1 coluna sempre)

5. _selo.html
   - Aceita `kind` (resenha|aberto|quebrado|historico|multi)
   - Border 1px currentColor, padding 4px 8px, radius 2px
   - Public Sans 11px peso 500, UPPERCASE, letter-spacing 0.04em
   - Mapa de cores: ver README seção Componentes

6. _chip.html
   - Vocabulário controlado (epistemologias/teorias)
   - bg-paper-2 border-rule padding 4px 10px radius pílula
   - Aceita parâmetro `removable` (adiciona ×)

7. _btn.html
   - Variantes: primary, secondary, ghost
   - Modificador: sm
   - Min-height 44px (sm: 36px), radius 2px

Use SVG inline para ícones (objeto Icon em ui-shared.jsx tem todos).
NÃO use bibliotecas de ícones externas.

Crie templates/_base.html com:
- <!doctype html>, <html lang="pt-BR">
- <head> com fonts.css, tailwind output, htmx
- {% block content %}{% endblock %}
- Inclui _nav_desktop em md+ e _nav_mobile em md-
- Inclui _footer
```

**Critério de aceite:** uma URL de teste estendendo `_base.html` mostra
nav + footer corretos em mobile e desktop, com tipografia certa.

---

## Fase 3 — Modelos + fixtures

**Objetivo:** dados reais no banco para alimentar as telas.

**Prompt para executar:**

```
Crie os modelos Django conforme o esqueleto em design_handoff_anco/README.md
seção "Modelos Django sugeridos".

Apps:
- acervo/models.py com: BibBase (choices), Epistemology, Theory,
  KnowledgeArea, Work, Analysis, Review.

Particularidades importantes:
- Analysis.slug é único, formato "<ano>-<sobrenome>-<palavra>" (ex: 2025-santos-quilombola)
- Analysis.epistemology e theory_of_reference são M2M para vocabulário controlado
- Analysis.is_legacy=True marca acervo histórico
- Work.link_status: choices=[("ok","ok"),("broken","broken")]
- Work.bib_base: choices fixos = WoS, Scopus, ScienceDirect, Redalyc, Sage, RepositorioUFBA

Crie data migrations para popular:
1. Vocabulário controlado (Epistemology, Theory, KnowledgeArea) — ver
   design_handoff_anco/mockups/screen-acervo.jsx, função FiltersSidebar,
   para a lista exata de valores.
2. 8 fixtures de Analysis a partir de SEARCH_RESULTS em screen-acervo.jsx
   (criar Work + Analysis + analyst User).
3. 1 fixture detalhada da análise de Santos & Almeida (quilombolas) com
   TODOS os 13 campos preenchidos e resenha crítica completa — ver
   constante ANALYSIS em screen-analise.jsx.

Configure admin.py para todos os modelos com list_display útil.
```

**Critério de aceite:** `python manage.py migrate` aplica tudo, admin
mostra os 8 análises listadas, e a análise dos quilombolas tem os 13
campos preenchidos.

---

## Fase 4 — Tela 1 · Vitrine (homepage)

**Objetivo:** homepage estática ligada aos dados reais.

**Prompt para executar:**

```
Leia design_handoff_anco/README.md seção "Tela 1 · Vitrine".
Abra design_handoff_anco/mockups/screen-vitrine.jsx em paralelo —
ele contém a microcopy exata e os valores numéricos.

Crie templates/vitrine.html estendendo _base.html. Implemente as seções:

1. Hero (duas colunas desktop 1.4fr/1fr, uma mobile)
2. Métricas — grid 4 colunas desktop, 2x2 mobile, com hairlines.
   Os valores devem vir de queries reais:
   - Analysis.objects.count()
   - User.objects.filter(analyses__isnull=False).distinct().count()
   - Work.objects.values('bib_base').distinct().count()
   - "{min}-{max}" do Work.year
3. Lista de 5 análises mais recentes (ordenadas por published_at desc).
   No desktop, grid 120px / 1fr / 220px. No mobile, vertical.
   Renderize selos via {% include "partials/_selo.html" with kind=... %}.
4. Bloco metodologia + como contribuir — duas colunas desktop, fundo paper-2.
   Texto literal de screen-vitrine.jsx.

Crie views.py com VitrineView (TemplateView) que injeta os 4 valores
de métrica e queryset de recentes. Rota raiz / aponta para ela.

Microcopy do H1 (literal):
"O que a literatura científica diz sobre Análise Cognitiva, organizado
por quem a pratica."
Com a expressão "Análise Cognitiva" em <em>italic</em>.
```

**Critério de aceite:** abrir `/` mostra a homepage idêntica ao mock
desktop em viewport 1280px, e idêntica ao mock mobile em viewport 375px.

---

## Fase 5 — Tela 3 · Página de análise

**Objetivo:** documento citável renderizado a partir de uma instância
de `Analysis`.

> Por que pular do Acervo direto pra Análise? Esta é a tela mais
> importante; validar a renderização dos 13 campos primeiro evita
> retrabalho. O Acervo (Fase 6) precisa linkar pra ela de qualquer jeito.

**Prompt para executar:**

```
Leia design_handoff_anco/README.md seção "Tela 3 · Página de análise".
Abra design_handoff_anco/mockups/screen-analise.jsx em paralelo.

Crie templates/analise_detail.html.

Estrutura (estende _base.html):

1. Breadcrumb — "Acervo / {area} / análise"
2. Cabeçalho da análise (max 900px centered desktop):
   - Linha de selos (resenha crítica, acesso aberto, etc.) - condicional
   - Eyebrow "Análise de" em gold-deep
   - H1 .t-display com title da Work
   - Autores · *journal italic*, vol., n., p., ano
   - DOI em mono linkado a https://doi.org/{doi}
   - Botões: "Acessar obra original ↗" + "Snapshot Internet Archive"
3. Bloco de resenha crítica (somente se analysis.review_text):
   - Fundo review-bg, hairlines superior/inferior review-rule
   - Eyebrow "Resenha crítica" em gold-deep
   - Subtítulo "revisão cega por dois pares" italic ink-3
   - Texto Newsreader 19px (17 mobile), line-height 1.6, max-width 700px
   - DROP CAP na primeira letra do primeiro parágrafo (CSS ::first-letter)
   - Quebrar texto por \n\n em parágrafos
4. Body duas colunas desktop (max-width 1180px):
   - Coluna principal (max 720px): 13 campos da grade. Cada campo:
     - Label uppercase 11px ink-3 letter-spacing 0.12em
     - Valor: <p class="t-prose"> OU lista de chips (epistemology, theory)
     - Hairline inferior var(--rule)
     - **CRÍTICO:** se o campo estiver vazio/null/[], NÃO RENDERIZAR
       (nem label nem container). Use {% if %} em torno de cada bloco.
   - Sidebar sticky 280px:
     - "Nesta página" — anchors para as seções (use id= nos h2 acima)
     - "Análise rápida" — dl compacta com pertinência, define o conceito,
       base bibliográfica, tem resenha
     - URL estável em mono (request.build_absolute_uri)
5. Bloco de citação (max 720px, fundo paper-2):
   - ABNT formatada — gere via método Analysis.citation_abnt()
   - APA formatada — gere via método Analysis.citation_apa()
   - Botão "copiar" para cada (JS via navigator.clipboard.writeText)
6. Rodapé de metadados (hairline forte superior, max 720px, 2 colunas):
   - Autoria & revisão — analyst.full_name + reviewers estruturais nominais
     + "revisor A · revisor B" italic para revisão da resenha (cega)
   - Versionamento & licença — versão atual, link "histórico (N)",
     data de publicação, "CC BY-NC 4.0 — atribuição obrigatória, uso não-comercial"

URL pattern: /a/<slug:slug>/

Crie AnalysisDetailView (DetailView, model=Analysis, slug_field='slug').

No model Analysis, adicione métodos citation_abnt() e citation_apa()
que geram as strings literais (formatos exatos em ANALYSIS.abnt/apa
em screen-analise.jsx).
```

**Critério de aceite:** `/a/2025-santos-quilombola/` renderiza a página
inteira, idêntica ao mock. Selos coloridos no topo. Drop cap funcional.
Citações copiáveis.

---

## Fase 6 — Tela 2 · Acervo de busca

**Objetivo:** listagem pública filtrável, com busca textual e (depois)
semântica.

**Prompt para executar:**

```
Leia design_handoff_anco/README.md seção "Tela 2 · Acervo de busca".
Abra design_handoff_anco/mockups/screen-acervo.jsx em paralelo.

Crie templates/acervo.html.

Estrutura:

1. Header de busca — duas colunas desktop:
   - Eyebrow "Acervo público · {N} análises", H1 .t-display "Buscar no acervo"
   - Caixa de busca alta (56px desktop / 48px mobile), borda 1.5px ink
   - Botão "BUSCAR" preto sólido (uppercase, letter-spacing 0.04em)
   - Toggle "Busca textual" ↔ "Busca por significado" (badge italic
     "VETORIAL" no segundo). Use radio inputs estilizados como pílula.

2. Faixa de filtros ativos (border-bottom rule-strong):
   - Chips removíveis com formato "[grupo:] valor ×"
   - Direita: contagem, "ordenar por" dropdown, "exportar CSV"

3. Body duas colunas desktop (260px sidebar / 1fr resultados):
   - Sidebar de filtros (drawer no mobile via HTMX):
     * Ano (slider de intervalo, range 2018-2025)
     * Base bibliográfica (checkboxes com contagem por valor)
     * Área do conhecimento (checkboxes)
     * Epistemologia (checkboxes — vocab controlado)
     * Teoria de referência (checkboxes — vocab controlado)
     * Características da análise (collapsible)
     * Acesso & estado (collapsible)
   - Lista de resultados — grid 1fr/200px:
     * Selos no topo (condicionais)
     * Título Newsreader 19px peso 500 — link para /a/<slug>/
     * Autores · *journal italic*, ano · base
     * Snippet Newsreader 14px ink-2
     * Direita: % similaridade (visível apenas em modo semântico),
       "analisado por X" + data

4. Paginação — "mostrando 1-N de M" + botões numerados

Views:

class AcervoView(ListView):
    template_name = "acervo.html"
    paginate_by = 8
    context_object_name = "results"

    def get_queryset(self):
        qs = Analysis.objects.published().select_related('work', 'analyst')
        # filtros via GET params: q, semantic, base, year_min, year_max,
        # area, epistemology, theory, has_review, open_access, link_status
        # ...
        return qs

HTMX:
- Cada filtro: hx-get="/acervo/" hx-target="#results-container"
  hx-swap="outerHTML" hx-include="form#filters"
- Toggle textual/semântico: hx-get com semantic=1
- Botão "carregar mais" no mobile: hx-get com cursor

Para busca semântica, deixe um placeholder: por enquanto retorne
similaridade=0 e ordene por id. Adicione comentário TODO indicando que
a integração com pgvector + embeddings é fase posterior.
```

**Critério de aceite:** `/acervo/` lista as 8 análises. Filtros aplicam
sem reload (HTMX). Toggle textual/semântico mostra/esconde % similaridade.
Cada resultado linka para a página de análise.

---

## Fase 7 — Acessibilidade & polimento

**Prompt para executar:**

```
Auditoria final:

1. Rode Lighthouse e AXE em cada uma das 3 telas. Corrija qualquer issue
   de contraste, label faltante, role faltante, ou heading order.

2. Navegação por teclado: Tab atravessa todos os elementos interativos
   numa ordem lógica. Foco visível (outline 2px gold).

3. Reduced motion: respeite prefers-reduced-motion (HTMX transitions OFF).

4. Imagens: nenhuma na home/acervo/análise atualmente. Se aparecer,
   alt obrigatório.

5. Form labels: toda <input> tem <label> visível ou aria-label.

6. Live regions: filtros do acervo via HTMX devem anunciar mudanças
   (aria-live="polite" no contêiner de resultados).

7. Print stylesheet: a página de análise deve imprimir bem
   (sem nav, sem sidebar, página A4).
```

**Critério de aceite:** Lighthouse Accessibility ≥ 95 nas 3 telas.

---

## Fora do escopo (fases futuras)

- **Formulário de cadastro de análise (analista logado)** — multipasso,
  4 passos, com auto-save HTMX a cada blur. Especificação completa virá
  num handoff complementar.
- **Fluxo de revisão por pares** — atribuição automática, decisão,
  versionamento.
- **Busca semântica vetorial** — integração pgvector + embeddings
  (OpenAI ou local). UI já está pronta.
- **Captura Internet Archive** — botão na análise dispara save ao
  archive.org via API.
- **Exportação CSV** — endpoint que exporta resultados filtrados.

---

## Convenções gerais

- **Commits:** uma fase = uma sequência de commits coesos. Mensagem
  inicia com "fase N: ".
- **Templates:** sempre `{% load static %}` no topo. Use `{% url %}` para
  rotas, nunca hardcode.
- **HTMX:** sempre devolva fragmento HTML, nunca JSON, em endpoints
  consumidos por HTMX. JSON apenas em APIs explícitas (não há ainda).
- **Microcopy:** **literal** dos mocks. Não traduzir, não parafrasear.
  Em caso de dúvida, abra o `.jsx` correspondente e copie textualmente.
- **Cores:** **somente** as listadas em tokens. Adicionar uma cor nova
  exige discussão.

---

## Validação visual

Ao final de cada fase de UI (4, 5, 6), abra lado a lado:

- A tela implementada em `localhost:8000` no Chrome em viewport 375px
  e 1280px (DevTools → toggle device).
- O mock correspondente em
  `design_handoff_anco/mockups/AnCo — Mockups.html`.

A diferença visual deve ser **imperceptível**. Se houver diferença,
ajuste antes de avançar.
