# Relatório — Fase Frontend 2: Vitrine (homepage)

## O que foi entregue

- `apps/publico/views.py` — `vitrine_view` com 4 queries de métricas reais + 5 análises recentes
- `templates/vitrine.html` — página completa estendendo `_base_publico.html`
- `config/urls.py` — rota `/` agora serve `vitrine_view` (era `home_view`)

## Critério de aceite (da especificação)

- [x] Hero com H1 editorial, texto âncora em itálico ("Análise Cognitiva"), dois CTAs
- [x] Bloco de métricas 4-col desktop / 2×2 mobile com dados reais do banco
- [x] Lista das 5 análises mais recentes com selos, autor e data formatada em pt-BR
- [x] Seção metodologia + como contribuir em duas colunas (paper-2 background)
- [x] Layout responsivo: hero, métricas e lista adaptam mobile ↔ desktop via `<style>` inline com media queries

## Decisões tomadas

**Dados reais desde o dia 1:** a vitrine carrega métricas ao vivo — 1.095 análises, 81 pesquisadores, 6 bases, amplitude 1999–2024. Não há cache; em volume pequeno isso é negligível.

**Datas formatadas no view:** o Django `date:"N"` com `LANGUAGE_CODE=pt-br` gerava "Abril." em vez de "abr.". Optei por formatar datas em Python no view com um dict `_MESES_PT`, tornando o template trivial e eliminando dependência de locale do SO.

**`recentes` como lista de dicts:** o view entrega `[{"analise": ..., "data_fmt": "..."}]` em vez de um queryset bruto, evitando lógica de data no template.

**`home_view` preservado:** `apps/core/views.py` ainda tem `home_view` e `templates/core/home.html`. Não foram deletados — são código morto controlado; remoção fica para limpeza pós-go-live.

**Media queries via `<style>` inline:** seguindo o padrão dos mockups (que usam estilos inline), a responsividade é controlada por um bloco `<style>` no topo do `{% block content %}`. Não conflita com Tailwind; não polui o design system.

**`href` hardcoded em dois botões do hero:** os CTAs "Explorar o acervo" e "Entrar para contribuir" usam `/acervo/` e `/accounts/login/` diretamente em vez de `{% url %}`, porque os parciais `_btn.html` recebem `href` via `include with` e não suportam template tags no argumento.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| Métricas: "6 bases bibliográficas" | Conta real: 6 | Coincidência — dados reais |
| Amplitude: "2008–25" | Exibe "1999–24" | Dados reais do acervo |
| `home_view` substituída | URL `/` trocada; `home_view` existe mas não é roteada | Remoção fica para cleanup |

## Dívida técnica deixada

- `apps/core/views.py:home_view` e `templates/core/home.html` são código morto — remover antes do go-live
- CTAs do hero com href hardcoded (`/acervo/`, `/accounts/login/`) — aceitável enquanto as URLs não mudam
- Sem cache nas queries de métricas — se o acervo crescer muito, adicionar `cache_page` ou memoização

## Métricas

- Arquivos criados: 2 (`templates/vitrine.html`, este relatório)
- Arquivos modificados: 2 (`apps/publico/views.py`, `config/urls.py`)
- HTTP 200 confirmado em produção via `Host: anco.paulovicente.pro.br`
- Dados reais: 1.095 análises · 81 pesquisadores · 6 bases · 1999–2024

## Pendências para o usuário

- Abrir `https://anco.paulovicente.pro.br/` e validar visualmente a vitrine
- Confirmar se os dados exibidos (métricas, análises recentes) estão corretos
- Aprovar para seguir para Fase 3 — Página de Análise
