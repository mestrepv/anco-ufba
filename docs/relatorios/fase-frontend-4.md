# Relatório — Fase Frontend 4: Acervo (listagem facetada)

## O que foi entregue

- `templates/publico/listagem.html` — reescrito com o design system editorial
- `apps/publico/views.py` — `listagem_view` ampliada com `active_nav`, `n_filtros_ativos`, `ordenar_label`

## Critério de aceite (da especificação)

- [x] Header 2-col desktop (eyebrow + H1 / caixa de busca)
- [x] Caixa de busca com input estilizado e botão "Buscar" integrado
- [x] Sidebar de filtros desktop (sempre visível) com grupos colapsáveis via `<details>`
- [x] Filtros: Ano, Base bibliográfica, Características (resenha/acesso aberto), Status
- [x] Botão "Aplicar filtros" + link "limpar filtros" na sidebar
- [x] Filtros mobile colapsáveis via `<details>` (sem JS)
- [x] Chips de filtros ativos na barra de resultados
- [x] Linha de resultado: selos, título linkado, metadados, trecho do resumo (desktop)
- [x] Coluna direita (desktop): analista + data
- [x] Linha mobile compacta: analyst + data em uma linha
- [x] Paginação windowed: página atual ± 2, sempre 1 e última, com ellipsis

## Decisões tomadas

**Um form para busca, outro para filtros:** a busca em `/acervo/?q=...` limpa os filtros ativos (novo ponto de partida), enquanto o form de filtros preserva `q` via hidden input. Este é o UX correto: busca nova → começa do zero; filtros → refinam a busca atual.

**`<details>` + `display:contents` para sidebar/mobile:** no desktop, o `<details>` externo dos filtros recebe `display:contents` via CSS, tornando-se transparente e expondo sempre os grupos. No mobile, funciona normalmente como drawer colapsável. Sem JS.

**Paginação windowed em template Django puro:** o template itera `pagina.paginator.page_range` e mostra: página atual ± 2, sempre primeira e última, com `…` quando há lacuna. Para 1095 análises (55 páginas), o resultado é limpo.

**Snippet = `artigo.resumo`:** o trecho exibido em cada resultado (desktop only) usa `{{ analise.artigo.resumo|truncatechars:200 }}`. O campo já está na query via `select_related`. Sem query extra.

**Selo `multi` não implementado:** o mockup mostra "múltiplas análises" para artigos com >1 análise publicada. A view atual não computa essa informação (exigiria `annotate(Count('artigo__analises'))`). Adiado — pode ser adicionado ao view quando demandado.

**`ordenar_label` para exibição:** a view calcula o label textual ("relevância" se há busca, "mais recentes" se não há) e passa para o template. Sem select de ordenação por enquanto.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| Filtro por Epistemologia e Teoria | Não implementado | `_FACETAS` do view não inclui essas facetas; a query seria custosa sem índice específico |
| Slide range para Ano | Checkboxes por ano | Range slider requer JS; checkboxes são funcionais e acessíveis |
| Botão "Exportar CSV" | Link "↓ planilha" para `/acervo/planilha/` | A planilha já existe; exportação CSV real fica para fase futura |
| Selo "múltiplas análises" | Não renderizado | Query de contagem por artigo não disponível no view atual |
| Busca semântica ("por significado") | Não implementado | Feature de fase futura (Phase 6) |

## Dívida técnica deixada

- Filtros de Epistemologia e Teoria de referência seriam valiosos — requerem `annotate` + índice no view
- Selo `multi` requer `annotate(n_analises=Count('artigo__analises__status', filter=...))` na query
- Busca semântica (vetorial) planejada para Fase 6

## Métricas

- Arquivos modificados: 2 (`templates/publico/listagem.html`, `apps/publico/views.py`)
- Arquivos criados: 1 (este relatório)
- HTTP 200 confirmado em `/acervo/` e `/acervo/?q=cogni%C3%A7%C3%A3o`
- Busca textual funcional: 34 resultados para "cognição" em 1.095 análises
- Paginação: 1–20 de 1095, 55 páginas, windowed corretamente

## Pendências para o usuário

- Abrir `https://anco.paulovicente.pro.br/acervo/` e validar visualmente
- Testar uma busca textual e um filtro de base bibliográfica
- Confirmar aprovação para seguir para Fase 5 — A11y + SEO audit
