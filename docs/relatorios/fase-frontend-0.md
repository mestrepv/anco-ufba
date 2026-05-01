# Relatório — Fase Frontend 0: Preparação do ambiente

## O que foi entregue

- `pytailwindcss>=0.2,<0.3` adicionado às dependências de dev em `pyproject.toml`
- `infra/Dockerfile` atualizado com passo de build Tailwind (`python -m pytailwindcss`)
- `tailwind.config.js` criado com todos os design tokens (mantido como documentação; v4 usa `@theme` no CSS)
- `static/css/input.css` — fonte do Tailwind v4 com `@theme`, `@layer base` e `@layer components` contendo toda a escala tipográfica e componentes do design system
- `static/css/fonts.css` — declarações `@font-face` com unicode-range para latin + latin-ext (subsets relevantes para pt-BR)
- `static/fonts/newsreader/` — 4 arquivos woff2 (roman + italic, variável, subsets latin/latin-ext)
- `static/fonts/public-sans/` — 4 arquivos woff2 (roman + italic, variável, subsets latin/latin-ext)
- `static/fonts/jetbrains-mono/` — 2 arquivos woff2 (Regular 400 + Medium 500)
- `templates/_base_publico.html` — base template do design system editorial (separado do `_base.html` interno)
- `.gitignore` atualizado: `static/css/output.css` excluído (arquivo gerado)

## Critério de aceite (da especificação)

- [x] Servidor Django roda — container `infra-web-1` em execução
- [x] Tailwind compila sem erros — `Done in 735ms`, output.css 30KB

## Decisões tomadas

**Tailwind v4 em vez de v3:** `pytailwindcss` (todas as versões disponíveis) baixa o binário mais recente do Tailwind CLI do GitHub, que hoje é v4.2.4. Não é possível forçar v3 via este pacote. Adotou-se v4 com a sintaxe nativa (`@import "tailwindcss"`, `@theme { }`). As utilidades de layout (`flex`, `grid`, `px-*` etc.) e as cores customizadas funcionam identicamente ao v3 — diferença é apenas na configuração.

**`tailwind.config.js` preservado:** mantido como documentação dos tokens, mas não é lido pelo Tailwind v4 (que usa `@theme` no CSS). Pode ser removido futuramente.

**Fonte `JetBrains Mono` sem subsets unicode-range:** os arquivos baixados do GitHub release são monolíticos (sem split por unicode-range), o que é correto — fontes mono geralmente não precisam de subsetting.

**Fontes servidas via Google Fonts CDN indiretamente:** os arquivos woff2 foram baixados da CDN `fonts.gstatic.com` para servir localmente. Licença SIL OFL 1.1 para todas as três famílias.

**`python -m pytailwindcss` no Dockerfile:** o instalador da v0.2.0 não coloca o executável no `$PATH` do container; usar `python -m` resolve.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| Tailwind CSS 3.x | Tailwind CSS v4.2.4 | pytailwindcss não oferece v3; v4 é funcionalmente equivalente para o uso do projeto |
| `@layer components` com `@apply` | Classes escritas com CSS puro (sem `@apply`) | Desnecessário — o design system tem poucas classes e CSS puro é mais legível |

## Dívida técnica deixada

- `tailwind.config.js` pode ser deletado (não é usado pelo v4) — fica por ora como documentação
- Comando de watch para dev (`python -m pytailwindcss -i ... -o ... --watch`) não está documentado em Makefile/README

## Métricas

- `output.css` gerado: 30KB minificado
- Fontes instaladas: 10 arquivos woff2, ~1.1MB total
- Arquivos criados/modificados: 10

## Pendências para o usuário

- Nenhuma. Pronto para iniciar Fase 1 (parciais base).
