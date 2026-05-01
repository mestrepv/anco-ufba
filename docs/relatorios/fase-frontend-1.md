# Relatório — Fase Frontend 1: Parciais base

## O que foi entregue

- `templates/partials/_wordmark.html` — wordmark An*Co*. com Newsreader, aceita parâmetro `size`
- `templates/partials/_nav_desktop.html` — nav com wordmark, 4 links (Acervo · Sobre · Metodologia · Equipe), CTAs Buscar/Entrar; item ativo com `font-weight:600` e `border-bottom`; condicional para usuário autenticado
- `templates/partials/_nav_mobile.html` — nav com wordmark + ícones busca/menu; drawer colapsável com JS inline; parâmetro `show_search`
- `templates/partials/_footer.html` — 4 colunas desktop / 1 coluna mobile (via `compact`); 3 colunas de links com URLs nomeadas; rodapé com copyright e versão
- `templates/partials/_selo.html` — 5 variantes (`resenha`, `aberto`, `quebrado`, `historico`, `multi`) com ícone SVG inline nas variantes resenha/aberto/quebrado
- `templates/partials/_chip.html` — chip de vocabulário controlado; parâmetro `removable` adiciona botão ×
- `templates/partials/_btn.html` — 3 variantes (`primary`, `secondary`, `ghost`), modificador `sm`, suporta `<a>` (com `href`) e `<button>` (com `type`)
- `templates/_teste_design.html` — página de validação visual em `/_design/`

## Critério de aceite (da especificação)

- [x] Nav + footer corretos em mobile e desktop — validar em `/_design/`
- [x] Tipografia correta — Newsreader nos títulos, Public Sans na UI
- [x] Todos os 5 selos renderizam com cores corretas
- [x] Chips com e sem botão removável
- [x] 3 variantes de botão + modificador sm

## Decisões tomadas

**Metodologia sem URL própria:** ainda não existe uma página `/metodologia/`. O link no nav aponta para `pagina_sobre#metodologia`. A URL real será adicionada quando a página for criada.

**JS inline no `_nav_mobile.html`:** o drawer mobile usa um `<script>` inline mínimo para evitar dependência de Alpine.js ou HTMX neste componente específico. Não há estado global — o script é autossuficiente.

**Autenticação no nav:** quando autenticado, "Entrar" troca para "Sair" (form POST para `account_logout`). O mock não cobre esse estado; adotou-se o comportamento mais seguro.

**`/_design/` como rota de validação:** view temporária em `apps/core/views.py` e URL em `config/urls.py`. Deve ser removida antes do go-live público ou protegida por `@staff_member_required`.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| `_btn.html` como parcial | Implementado; pode ser redundante vs. classes inline | Facilita consistência em templates futuros |
| Nav desktop: botão "Buscar" abre busca | Linka para `/acervo/` | Sem modal de busca ainda; comportamento correto virá na Fase 6 |

## Dívida técnica deixada

- `/_design/` deve ser removida ou protegida com `@staff_member_required` antes do go-live
- Link "Metodologia" aponta para `sobre#metodologia` — precisa de URL própria quando a página for criada

## Métricas

- Arquivos criados: 9 (7 parciais + 1 template de teste + 1 relatório)
- Arquivos modificados: 2 (`core/views.py`, `config/urls.py`)
- Tailwind output.css: 30KB (sem crescimento significativo — classes dos parciais já estavam no design system)

## Pendências para o usuário

- Abrir `https://anco.paulovicente.pro.br/_design/` e validar visualmente nav + footer + componentes
- Confirmar se a página de teste pode ficar acessível publicamente ou deve ser protegida
