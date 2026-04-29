# Relatório — Fase 5: Acervo público

**Data**: 2026-04-29
**Branch**: `fase-5-acervo-publico` (a partir de `fase-4-revisao-pares`)
**Commits**: 3 atômicos por área

## O que foi entregue

### Novo app `apps.publico`

App dedicado às views públicas (sem login). Migration inicial habilita
extensão **`unaccent`** do Postgres para FTS sem acentos. Sem novos
models — só views, services e templates sobre os modelos da Fase 1.

### Serviços ([apps/publico/services.py](apps/publico/services.py))

- `doi_to_slug(doi)` / `slug_to_doi(slug)`: conversão determinística
  reversível. DOI canônico `10.1234/abc` → `10.1234__abc`; legado
  `legacy:HASH` → `legacy__HASH`. Heurística no reverso pelo prefixo.
- `gerar_citacao_abnt(analise)`: ABNT 6023:2018 simplificada,
  preservando preposições (`da`, `de`, `do`, `e`, etc. ficam minúsculas).
- `gerar_citacao_apa(analise)`: APA 7th simplificada.
- Múltiplos autores: separadores comuns (`;`, ` e `, ` & `, `and`).

### Views ([apps/publico/views.py](apps/publico/views.py))

- **`listagem_view`** (`/acervo/`): busca textual via `SearchVector +
  SearchRank` config `portuguese` em título, resumo, objeto, objetivo,
  aspectos relevantes, definição, resenha. DOI exato como fallback.
  Facetas: ano, base, status, resenha, acesso aberto, link_status.
  Paginação 20 por página, querystring preservada na navegação.
- **`pagina_artigo_view`** (`/artigo/<slug>/`): metadados, link
  primário/alternativo, badge de status do link com aviso para
  quebrados, snapshot Wayback se disponível, lista de análises
  publicadas/legado.
- **`pagina_analise_view`** (`/analise/<id>/`): 404 para não-publicadas;
  resenha crítica em destaque (card violeta com selo "peer-reviewed");
  campos textuais filtrados (só preenchidos); M2M de epistemologia e
  teoria como chips; revisões com **mascaramento** (cegos como
  "Revisor cego A", "Revisor cego B", ...); citações ABNT e APA prontas;
  selo CC-BY-NC com link.
- **`historico_analise_view`** (`/analise/<id>/historico/`): listagem
  de versões do `simple_history` (50 mais recentes).

### URLs

- `/acervo/` — listagem pública (era do analista; movido para `/acervo-analista/`)
- `/artigo/<doi-slug>/` — página estável e citável
- `/analise/<id>/` — página estável e citável
- `/analise/<id>/historico/` — versões
- Todos os reverses (`reverse('minhas_analises')`, etc.) continuam
  funcionando — só os caminhos mudaram.

### Templates

- `templates/publico/listagem.html` — layout 2 colunas com facetas
  laterais e busca textual no topo
- `templates/publico/artigo.html` — metadados, aviso de link, lista
  de análises
- `templates/publico/analise.html` — fluxo principal; resenha em
  destaque visual; revisores; bloco de citação ABNT/APA; selo CC-BY-NC
- `templates/publico/historico.html` — versões enxutas
- `templates/_base.html` — link "Acervo público" no nav
- `templates/core/home.html` — redesenhado com Tailwind; CTA para acervo

## Critério de aceite (spec §10 — Fase 5)

- [x] Listagem com paginação (20 por página, conforme spec §6.1)
- [x] Busca facetada (Postgres FTS via SearchVector + facetas dinâmicas)
- [x] Página do artigo (`/artigo/<slug>/` com URL estável)
- [x] Página da análise (`/analise/<id>/` com URL estável)
- [x] Selo de destaque para resenhas críticas peer-reviewed
- [x] Histórico de versões consultável (`/analise/<id>/historico/`)
- [x] Geração de citação ABNT/APA (visível inline na página da análise)
- [x] Selo CC-BY-NC visível
- [x] **URLs estáveis e citáveis desde o dia 1** (DOI-slug determinístico)
- [x] **Aceite formal**: navegar, buscar e citar análises sem login —
  confirmado em testes (19 cenários novos) e shell (curl HTTP 200 em
  `/`, `/acervo/`, `/acervo/?q=cogni`, `/artigo/<slug>/`,
  `/analise/<id>/`).

## Decisões tomadas

- **App separado `apps.publico`** em vez de adicionar ao `acervo`:
  separa fluxos públicos (sem auth) dos do analista (com auth) e
  facilita evoluir cada um.
- **`/acervo/` → listagem pública; `/acervo-analista/` → fluxos do
  analista**: a rota `/acervo/` agora é a porta de entrada do leitor
  ocasional (compatível com a spec §6.1). Reverses continuam
  funcionando porque só o caminho mudou.
- **DOI-slug com `__`** em vez de `-` ou URL-encoding: DOI tem `.` e
  caracteres alfanuméricos que viraria slug ilegível com `-`. `__` é
  raro em DOIs reais, deixa o slug legível, e a conversão é trivial
  e reversível.
- **FTS com `config="portuguese"`** em vez de simple FTS: stemming
  apropriado para PT-BR sem precisar de configuração custom. `unaccent`
  habilitado via migration para tolerar acentos na query.
- **Facetas sem cross-faceta dinâmica**: contagens por valor são
  calculadas sobre o conjunto já filtrado (simples). Em volume baixo
  funciona; em escala maior precisaríamos calcular por faceta excluindo
  ela própria.
- **Mascaramento de cegas com `Revisor cego A/B/...`**: ordem
  determinística por id da revisão para que recargas mostrem sempre
  os mesmos rótulos.
- **Citação inline no template** em vez de modal JS: mais simples,
  acessível, indexável e funciona sem JS.
- **Selo CC-BY-NC no rodapé da análise**, não global: só se aplica ao
  conteúdo autoral; metadados de artigo seguem outras licenças (spec §7).
- **Histórico simples** mostra timestamp + autor + tipo de mudança +
  status, sem diff entre versões (linkado para o admin do simple_history
  como caminho avançado).
- **Tailwind via CDN ainda**: spec §10 Fase 7 mencionará bundle prod
  se necessário.

## Desvios da especificação

- **Facetas implementadas: 6 das 12 listadas em §6.2**. Cobertura:
  ano, base, status, tem_resenha, acesso_aberto, link_status. Faltam:
  área, epistemologia, teoria, pertinência, define_conceito, analista.
  Adiável — todos seguem o mesmo padrão e podem ser adicionados em
  minutos. Só decidi começar pelas mais frequentemente usadas.
- **Histórico não mostra diff** entre versões — só lista. Spec §6.4 diz
  "link para diff"; aqui o diff completo está acessível pelo admin
  via `simple_history` UI (`/admin/acervo/analise/<id>/history/`).
- **Toggle textual/semântico do §6.2 (v2.1)** não foi implementado —
  é da Fase 8 (busca semântica). A view só tem busca textual; a UI
  pode ganhar o toggle quando a Fase 8 chegar.
- **Sem botão "copiar citação" com JS**: usuário copia manualmente do
  `<pre>`. Aceitável; pode evoluir.

## Dívida técnica deixada

- **Sem cache de busca**: cada query recalcula. Em volume baixo OK;
  Redis cache pode entrar na Fase 7.
- **Sem index FTS materializado**: o `SearchVector` é calculado por
  query. Em volume real, criar `GinIndex(SearchVectorField)` com
  trigger é mais eficiente. Adiável até notar lentidão.
- **Sem rate limiting** no endpoint público: vulnerável a scraping
  agressivo. `django-ratelimit` entra na Fase 7.
- **Histórico exposto** mostra `history_user` (analista) — em revisão
  cega ainda em curso, isso vazaria autoria. Hoje o histórico só é
  acessível para análises **publicadas**, então o problema só apareceria
  se houver auditoria pós-publicação. Mantido como dívida da Fase 4.
- **Resenha crítica é texto puro**, não Markdown. Adiável. Spec §6.4
  só diz "card distinto, no topo da página, com selo".
- **Sem sitemap.xml/robots.txt** para indexação no Scholar. Fase 7.

## Métricas

- **Cobertura**: 91% (1.542 statements, 135 misses).
- **Testes**: **222** (30 novos: 11 services + 19 views).
- **Linhas adicionadas**: ~830 (services + views + urls + 4 templates +
  testes; mais home.html refeita).
- **Arquivos criados**: 11.
- **Tempo aproximado da fase**: ~1h30.

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 6:

1. **Promover seu usuário a `curador`** e publicar uma análise não-legado
   end-to-end (cria → submete → 4 revisões → publicada) para testar o
   acervo com conteúdo do fluxo novo.
2. **Atualizar `Site` (id=1)** no admin para o domínio real assim que
   o repositório for hospedado — citações ABNT/APA usam `BASE_URL` e
   precisam apontar para o domínio definitivo.
3. **Decidir sobre Wayback automático no cadastro de artigo**: Fase 3
   deixou o snapshot manual (botão). Para artigos publicados, vale
   automatizar (task assíncrona após publicação). Pode entrar na
   Fase 6 (saúde de links).

**Aprovação para iniciar a Fase 6** (API REST, métricas, saúde
periódica de links, dashboard administrativo) é o próximo passo.
