# Relatório — Fase 6: Saúde de links, dashboard e acesso machine-readable

**Data**: 2026-04-29
**Branch**: `fase-6-saude-links-dashboard` (a partir de `fase-5-acervo-publico`)
**Commits**: 6 atômicos por área

Esta fase foi **reescopada na v2.2 da especificação** após discussão
com o usuário. A API REST genérica e Swagger (`drf-spectacular`)
originalmente previstos foram **adiados para v2** por não haver
cliente real identificado (sem mobile, sem dashboard externo, sem
integração planejada). Em seu lugar, a fase entrega valor concreto:
saúde de links, ferramentas de curadoria e acesso machine-readable
sem novos endpoints.

## O que foi entregue

### Verificação periódica de links ([apps/acervo/tasks.py](apps/acervo/tasks.py))

`task_verificar_links(limite=0)`: itera artigos cujas análises são
publicadas/legado, faz HEAD via `validar_link` (reusa o serviço da
Fase 3), persiste `link_status` + `link_ultima_verificacao`. Exceções
individuais são logadas e contadas como "pulados" sem derrubar a task.

### Setup de schedules ([apps/acervo/management/commands/setup_q_schedules.py](apps/acervo/management/commands/setup_q_schedules.py))

Comando idempotente que cria/atualiza os schedules django-q2:
- `verificar_prazos_revisao` (DAILY) — reaproveita task da Fase 4
- `verificar_saude_dos_links` (WEEKLY) — nova

### Actions de manutenção de links no admin ([apps/acervo/admin.py](apps/acervo/admin.py))

`ArtigoAdmin` ganhou três actions em lote:
- **Re-verificar link** dos selecionados (chama `validar_link` e
  reporta total/ok/quebrado)
- **Promover snapshot Wayback** como link primário (substitui
  `link_acesso` pela URL do Wayback; se não houver snapshot, captura
  agora via Save Page Now)
- **Marcar como indisponível permanentemente** (bulk update de
  `link_status=quebrado`)

### Proxy "Links Quebrados" no admin

`LinkQuebrado` (proxy de `Artigo`) com changelist pré-filtrada por
`link_status=QUEBRADO`. Aparece como entrada separada no admin —
atalho de curadoria sem precisar configurar filtro toda vez.

### Widgets de dashboard no admin home ([apps/core/admin_dashboard.py](apps/core/admin_dashboard.py))

- `calcular_metricas()`: análises por status, revisões pendentes vs
  atrasadas, links quebrados, solicitações pendentes.
- `instalar_dashboard()`: patch idempotente do `admin.site.index` para
  injetar `dashboard` no contexto e apontar `index_template` para
  override custom. Configura `site_header`, `site_title`, `index_title`.
- Template `templates/admin/index_anco.html` estende
  `admin/index.html` e adiciona painel com 4 cards no topo. Cores
  destacam estados críticos (atrasos, links quebrados, solicitações
  pendentes); links diretos para changelists filtradas.

### JSON-LD nas páginas públicas ([apps/publico/schema.py](apps/publico/schema.py))

Embute `<script type="application/ld+json">` nas páginas públicas com:
- `schema.org/ScholarlyArticle` em `/artigo/<slug>/` (name, headline,
  datePublished, isPartOf Periodical, author array, abstract, url,
  isAccessibleForFree, sameAs/identifier para DOIs canônicos).
- `schema.org/Review` em `/analise/<id>/` com `itemReviewed`
  aninhando o ScholarlyArticle, autoria do analista, license
  CC-BY-NC, publisher AnCo, `reviewBody` quando há resenha.

DOIs `legacy:HASH` não geram URL `doi.org` (são identificadores
internos, não DOIs reais).

## Critério de aceite (spec §10 Fase 6 v2.2)

- [x] Tarefa periódica de verificação de links (cron semanal via
  `Schedule`)
- [x] Changelist "Links quebrados" no admin com 3 actions em lote
- [x] Widgets de dashboard no admin home (4 cards)
- [x] JSON-LD embutido nas páginas públicas
- [x] Setup de schedules via management command idempotente

API REST + Swagger **adiados para v2** (registrado em §14).

## Decisões tomadas

- **Patch do `admin.site.index`** em vez de subclasse `AdminSite`
  customizada: menos invasivo, não exige reconfigurar todos os
  `@admin.register` calls, idempotente.
- **`templates/admin/index_anco.html`** em vez de `index.html`:
  evita loop de extends. Configurado via `admin.site.index_template`.
- **Proxy `LinkQuebrado`**: `class Meta: proxy = True` reusa a tabela
  `Artigo` mas aparece como app separado no admin. Sem migration
  adicional.
- **`promover_snapshot_wayback` síncrono**: chamada ao Internet Archive
  pode demorar até 30s. Em fluxo curatorial pontual aceitável; se
  virar gargalo, mover para task assíncrona.
- **`task_verificar_links` itera só artigos com análise publicada/legado**:
  evita gastar HTTP requests em rascunhos/submetidas. Fluxo curatorial
  pode forçar via action manual.
- **JSON-LD inline (não endpoint separado)**: Scholar/Zotero indexam
  HTML; ter `application/ld+json` no `<head>` é o caminho canônico do
  schema.org. Zero endpoints novos. Evita rota duplicada.
- **`@type: Review` para a página da Análise** (não outro tipo
  qualquer): a AnCo realmente é uma plataforma que faz reviews de
  artigos. `Review.itemReviewed` aninha o ScholarlyArticle revisado.
- **DOIs `legacy:` não viram `doi.org`**: são IDs internos, não DOIs
  reais; expor como tal seria desinformação.
- **Sem `bibo`/`fabio`/`citoid` ontologies**: schema.org cobre o
  necessário e tem suporte universal nos consumidores.

## Desvios da especificação

- **API REST + Swagger ausentes**: documentado em §14 como adiado
  para v2 (decisão de v2.2).
- **`task_verificar_links` não filtra por `link_ultima_verificacao`
  recente**: em teoria, artigos verificados ontem não precisariam ser
  re-verificados hoje. Adicionar `last_checked > now - 6 days` cortaria
  trabalho repetido. Adiável; volume atual (~951 artigos) executa em
  poucos minutos.
- **Dashboard não tem cobertura de revalidação** (spec original
  mencionava). Pode ser adicionado como métrica em
  `calcular_metricas` quando relevante.

## Dívida técnica deixada

- **JSON-LD pode crescer**: hoje campos são limitados a ~5000 chars
  (`abstract`, `reviewBody`). Para análises com texto longo, isso
  trunca. Aceitável — Scholar não precisa de `abstract` completo
  para indexar, e o usuário sempre pode visitar a página.
- **`promover_snapshot_wayback`** captura síncrono se não houver
  snapshot. Se o IA estiver fora ou lento, a action trava. Mover para
  task assíncrona em fase futura quando virar problema.
- **Sem opção de "exclusão permanente" de artigo**: spec §5.7 menciona
  "marcar indisponível permanentemente". Hoje só atualizamos
  `link_status`. Se for preciso comportamento diferente (ex: ocultar
  do acervo público), adicionar campo dedicado.
- **Dashboard sem refresh automático**: o admin home recalcula
  on-demand a cada GET. Em volume alto isso fica caro. Cache simples
  com Redis (5 min TTL) resolveria; dívida adiável.
- **Sem teste de mock-real do Save Page Now**: action
  `promover_snapshot_wayback` mockada. Em testes E2E reais com IA pode
  falhar — mas o ServiceNet já é coberto na Fase 3.

## Métricas

- **Cobertura**: 92% (1.689 statements, 142 misses).
- **Testes**: **248** (26 novos: 10 Fase 6 + 16 schema/JSON-LD).
- **Linhas adicionadas**: ~880 (services + admin + dashboard +
  schema + 2 templates + 2 arquivos de teste + management command).
- **Arquivos criados**: 6.
- **Tempo aproximado**: ~50 min.

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 7:

1. **Subir o worker django-q2 em prod** (`docker compose --profile
   worker up -d`) e rodar `manage.py setup_q_schedules` uma vez para
   ativar os crons. Em dev sync-mode dispensa.
2. **Validar JSON-LD** com [Google Rich Results Test](https://search.google.com/test/rich-results)
   após o site estar publicamente acessível — confirma que
   Scholar/Zotero conseguem consumir.
3. **Considerar BibTeX/RIS** export individual (botão na página da
   análise) se houver demanda — fica como enhancement de v2 conforme
   spec §14.

**Aprovação para iniciar a Fase 7** (Polimento e produção: backup
automatizado, Caddy + HTTPS, monitoring com Sentry/GlitchTip, páginas
estáticas, deploy em produção) é o próximo passo.
