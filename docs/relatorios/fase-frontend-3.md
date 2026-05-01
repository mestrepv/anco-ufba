# Relatório — Fase Frontend 3: Página de Análise

## O que foi entregue

- `templates/publico/analise.html` — reescrito do zero com o design system editorial
- `apps/publico/views.py` — `pagina_analise_view` ampliada com `link_obra`, `publicada_fmt`, `active_nav`

## Critério de aceite (da especificação)

- [x] H1 editorial com título completo (Newsreader 400, 28px mobile / 48px desktop)
- [x] Selos (resenha, acesso_aberto, histórico) no cabeçalho
- [x] Metadados do artigo: autores, periódico, volume/número/páginas/ano, DOI em mono
- [x] Botão "Acessar obra original" só aparece se há link no artigo
- [x] Resenha crítica em callout (review-bg, review-rule) com drop cap CSS, visível só quando `tem_resenha=True`
- [x] Grade completa dos 13 campos na ordem canônica, campos vazios ocultos
- [x] Chips de epistemologia e teoria de referência posicionados corretamente na grade
- [x] Sidebar desktop sticky: "Nesta página", "Análise rápida", URL estável
- [x] Bloco de citação ABNT + APA com botões "copiar" via `navigator.clipboard`
- [x] Rodapé de autoria (analista + revisores identificados por tipo) e versionamento (CC BY-NC 4.0)
- [x] Layout responsivo: sidebar oculta em mobile, grid 2-col em desktop

## Decisões tomadas

**Drop cap via CSS:** usada `::first-letter` com `float:left` em vez da abordagem JSX do mockup (que extraía `para[0]` no JS). A result visual é equivalente sem necessidade de filtro customizado.

**Grade em duas passagens:** `campos_textuais` é iterado duas vezes para intercalar os campos booleanos e os chips de vocabulário (que vêm direto do modelo) na posição correta. Campos excluídos por nome na primeira passagem aparecem na segunda, após epistemologia e teoria.

**`link_obra` pré-computado no view:** simplifica o template — não precisa fazer `|default` encadeado em dois campos URL.

**`publicada_fmt` como string formatada no view:** mesma estratégia da vitrine — evita dependência de locale do SO para formatar datas em pt-BR.

**DOI legado:** o template verifica se o DOI começa com "legacy:" antes de renderizar o link. Usa `|slice:":7"` em dois `{% if %}` aninhados para clareza.

**Sem cache de versão no header:** o mockup mostra "v.3 · 12 abr. 2026" mas a contagem real exige query extra. O link "ver histórico →" resolve a necessidade sem custo adicional.

**`tem_resenha=True` nunca ocorre no acervo legado:** todos os 1.095 registros têm `tem_resenha=False`. O bloco de resenha foi testado em leitura estática; entrará em produção real quando os primeiros analistas subirem resenhas.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| Sidebar com contagem de versões "v.3" | Link para histórico sem contagem | Evita query extra sem ganho real |
| Botão "Snapshot Internet Archive" | Não implementado | View não carrega `snapshot_recente` para análise; a info está na página do artigo |
| "Educação / análise" no breadcrumb desktop | "Acervo / análise" sem categoria | Categorização por área não existe no modelo |

## Dívida técnica deixada

- Snapshot Internet Archive não aparece na página da análise (está na do artigo)
- Contagem de versões no cabeçalho pode ser adicionada com `analise.history.count()` na view, se demandado

## Métricas

- Arquivos criados: 2 (`templates/publico/analise.html`, este relatório)
- Arquivos modificados: 1 (`apps/publico/views.py`)
- HTTP 200 confirmado em `/analise/1/` e `/analise/1095/`
- 13 campos renderizados na ordem canônica, chips corretos

## Pendências para o usuário

- Abrir `https://anco.paulovicente.pro.br/analise/1095/` e validar visualmente a página
- Confirmar aprovação para seguir para Fase 4 — Acervo (listagem facetada)
