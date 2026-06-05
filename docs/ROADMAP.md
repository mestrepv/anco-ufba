# Roadmap — Plataforma AnCo

> **Status vivo do roadmap**. Cada item dos critérios de aceite aqui é
> um espelho do escopo definido em [`ESPECIFICACAO.md` §10](ESPECIFICACAO.md);
> em conflito, a especificação prevalece.
>
> Cada fase concluída tem relatório detalhado em [`relatorios/`](relatorios/).

**Status atual**: 🎉 **Fases 0-7 concluídas!** Plataforma pronta para
deploy em produção. Fase 8 (busca semântica, opcional) permanece como
adendo da v2.1.

| # | Fase | Estimativa | Status | Relatório |
|---|------|-----------|--------|-----------|
| 0 | Fundação | 1 dia | ✅ concluída | [fase-0.md](relatorios/fase-0.md) |
| 1 | Núcleo de dados e admin | 2-3 dias | ✅ concluída | [fase-1.md](relatorios/fase-1.md) |
| 2 | Autenticação e cadastro | 1-2 dias | ✅ concluída | [fase-2.md](relatorios/fase-2.md) |
| 3 | Criação e edição de análises | 3-4 dias | ✅ concluída | [fase-3.md](relatorios/fase-3.md) |
| 4 | Revisão por pares | 3-4 dias | ✅ concluída | [fase-4.md](relatorios/fase-4.md) |
| 5 | Acervo público | 3-4 dias | ✅ concluída | [fase-5.md](relatorios/fase-5.md) |
| 6 | Saúde de links, dashboard e JSON-LD (v2.2) | 1-2 dias | ✅ concluída | [fase-6.md](relatorios/fase-6.md) |
| 7 | Polimento e produção | 2 dias | ✅ concluída | [fase-7.md](relatorios/fase-7.md) |
| 8 | Busca semântica | 3-4 dias | ⬜ pendente (opcional v2.1) | — |
| 13 | Revisão ANCO (modo simplificado + sorteio de análise) | — | ✅ concluída | [fase-13.md](relatorios/fase-13.md) |

---

## Fase 0 — Fundação ✅

Concluída em 2026-04-29. Relatório: [fase-0.md](relatorios/fase-0.md).

- [x] Estrutura Django + Docker Compose
- [x] Postgres, Redis (Caddy adiado para Fase 7 por escopo enxuto)
- [x] Settings dividido (`base.py`, `dev.py`, `prod.py`)
- [x] CI GitHub Actions: lint (ruff) + testes (pytest-django, cobertura ≥ 70%)
- [x] README com bootstrap local

## Fase 1 — Núcleo de dados e admin ✅

Concluída em 2026-04-29. Relatório: [fase-1.md](relatorios/fase-1.md).

- [x] Modelos completos (incluindo `SnapshotLink` e `resenha_critica`)
- [x] Migrations geradas e aplicadas
- [x] Admin Django configurado para os 9 modelos
- [x] `django-simple-history` integrado em `Analise`
- [x] Vocabulários iniciais via fixture
- [x] Script `migrate_legacy.py` idempotente para 1.443 registros
- [x] **Aceite**: `manage.py migrate_legacy` importa tudo; admin navegável

## Fase 2 — Autenticação e cadastro ✅

Concluída em 2026-04-29. Relatório: [fase-2.md](relatorios/fase-2.md).

- [x] `django-allauth` + Google OAuth configurados
- [x] Validação de domínio institucional (allowlist via env)
- [x] Tela de solicitação de promoção
- [x] Notificação aos curadores (signal + e-mail)
- [x] Aprovação promove `leitor → analista`
- [x] **Aceite**: leitor solicita promoção, curador aprova pelo admin,
  papel do user muda para `analista` (validado em testes e shell manual)

## Fase 3 — Criação e edição de análises ✅

Concluída em 2026-04-29. Relatório: [fase-3.md](relatorios/fase-3.md).

- [x] Busca/criação de Artigo com validação de link (HEAD request)
- [x] Integração Wayback Machine (botão "Capturar snapshot")
- [x] Formulário multipasso com HTMX (Identificação + Presença +
  Estrutura + Resenha)
- [x] Quarto passo opcional: Resenha Crítica
- [x] Auto-save a cada 30s (Alpine.js + endpoint JSON)
- [x] Submissão para revisão (`status: rascunho → submetida`)
- [x] Tailwind + HTMX + Alpine.js (via CDN nesta fase)
- [x] **Aceite**: criar análise completa do zero, com e sem resenha

## Fase 4 — Revisão por pares ✅

Concluída em 2026-04-29. Relatório: [fase-4.md](relatorios/fase-4.md).

- [x] Sorteio automático: 2 estruturais + 2 cegos (se há resenha)
- [x] Worker `django-q2` (entra no compose; profile `worker` opcional em dev)
- [x] Tela "Minhas revisões pendentes"
- [x] Mascaramento de autoria nas revisões cegas (testado: nem
  `nome_exibicao` nem `username` vazam)
- [x] Formulário de revisão com comentários ancorados por 8 campos
- [x] Lógica de transição de status (todas as combinações)
- [x] Re-sorteio por prazo expirado (`task_verificar_prazos`)
- [x] Exclusão do autor e dos autores de outras análises do mesmo artigo
- [x] Fila de espera quando faltam revisores (sem persistir parciais)
- [x] **Aceite**: análise com resenha passa por 4 revisões com autoria
  oculta nas cegas e é publicada automaticamente

## Fase 5 — Acervo público ✅

Concluída em 2026-04-29. Relatório: [fase-5.md](relatorios/fase-5.md).

- [x] Listagem `/acervo/` com paginação (20/página)
- [x] Busca facetada (Postgres FTS com `unaccent` + 6 facetas)
- [x] Página do artigo (`/artigo/<doi-slug>/`)
- [x] Página da análise (`/analise/<id>/`)
- [x] Selo de destaque para resenhas críticas peer-reviewed
- [x] Histórico de versões consultável (lista; diff fica via admin)
- [x] Geração de citação ABNT e APA (inline na análise)
- [x] Selo CC-BY-NC visível no rodapé da análise
- [x] **URLs estáveis e citáveis desde o dia 1** (DOI-slug determinístico)
- [x] **Aceite**: navegar, buscar e citar análises sem login

## Fase 6 — Saúde de links, dashboard e JSON-LD ✅

Concluída em 2026-04-29 (escopo reescopado na **spec v2.2**: API REST
e Swagger adiados para v2 — ver §14). Relatório: [fase-6.md](relatorios/fase-6.md).

- [x] Tarefa periódica (semanal) de verificação de links via
  `task_verificar_links`
- [x] Setup de schedules django-q2 (`manage.py setup_q_schedules`)
- [x] Changelist "Links quebrados" no admin (proxy `LinkQuebrado`)
- [x] Actions em lote: re-verificar link, promover snapshot Wayback,
  marcar indisponível
- [x] Widgets de dashboard no admin home (4 cards: análises por status,
  revisões pendentes/atrasadas, links quebrados, solicitações pendentes)
- [x] JSON-LD (schema.org/ScholarlyArticle + Review) embutido nas
  páginas públicas — Scholar/Zotero/agregadores consomem direto do HTML
- [x] Validação anti-SSRF na verificação de links (já implementada na
  Fase 3)
- [⏸️] API REST + Swagger — adiados para v2 (spec §14)

## Fase 7 — Polimento e produção ✅

Concluída em 2026-04-29. Relatório: [fase-7.md](relatorios/fase-7.md).

- [x] Caddy 2 no compose com Let's Encrypt automático (profile `prod`)
- [x] Backup `pg_dump` diário (`manage.py backup_db` + `infra/backup/run.sh`)
- [x] [`RESTORE.md`](RESTORE.md) com procedimento e teste trimestral
- [x] Logs JSON estruturados em prod (sem dependência externa)
- [x] Sentry SDK integrado (DSN opcional)
- [x] Páginas estáticas: Sobre, Equipe, Termos, Privacidade
- [x] Rate limiting (allauth `ACCOUNT_RATE_LIMITS` + `django-ratelimit`
  na busca pública)
- [x] CSP restritiva via `django-csp` em prod
- [x] [`DEPLOY.md`](DEPLOY.md) com procedimento completo
- [x] Plano de redirecionamento permanente (DEPLOY.md §7)
- [⏳] **Deploy em produção real**: documentado e pronto, depende de
  recursos externos (DNS, OAuth credentials, S3) — fora do escopo do
  agente

## Fase 8 — Busca semântica ⬜

> Pré-requisito explícito: plataforma em produção (Fase 7 concluída) com
> acervo legado importado e algumas análises feitas no fluxo novo.
>
> Especificação canônica em [`ESPECIFICACAO.md` §10 Fase 8](ESPECIFICACAO.md).
> Adendo de origem (v2.1) preservado em [`fase8_adendo.md`](fase8_adendo.md)
> como artefato histórico.

- [ ] Container `embeddings` no compose (modelo local, sem API externa)
- [ ] Extensão `pgvector` habilitada no Postgres
- [ ] Campos `embedding*` em `Artigo` e `Analise` + índices HNSW
- [ ] Geração de embeddings via signal `post_save` + task `django-q2`
- [ ] Comando `manage.py reindexar_embeddings` para popular acervo existente
- [ ] Toggle "textual / por significado" em `/acervo`, com modo
  preservado em URL (`?modo=textual|semantico`)
- [ ] Cards diferenciados por tipo de resultado (Artigo / Análise / Resenha)
- [ ] Indicador de similaridade (0-100%) em cada resultado semântico
- [ ] Documento `docs/busca_semantica/avaliacao.md` com 10 queries
  representativas comparadas em ambos os modos
- [ ] Sem regressão na busca textual

## Frente UX Analista + lookup Crossref/ISBN ✅

> Frente fora da numeração de fases. Branch `feat/analista-ux-crossref`,
> concluída em 2026-05-01. Relatório em
> [`docs/relatorios/feat-analista-ux-crossref.md`](relatorios/feat-analista-ux-crossref.md).

- [x] Serviço de lookup DOI via Crossref com cache 24h
- [x] Serviço de lookup ISBN via OpenLibrary com cache 30 dias
- [x] `Artigo` aceita ausência de DOI (ISBN ou identificador interno
  determinístico `legacy:HASH`)
- [x] Forms divididos: `IdentificadorLookupForm` (lookup com detecção
  de tipo) + `ArtigoMetadadosForm` (campos editáveis)
- [x] View HTMX `lookup_identificador_view` com preview ao vivo
- [x] `cadastrar_artigo_view` reescrita para fluxo lookup → preview →
  POST
- [x] Design editorial em todas as telas do analista (`_base_publico`,
  tokens `.lookup-input`, `.field-input`, `.meta-card`, `.step-indicator`,
  `.badge-*`, `.spinner`)
- [x] Templates: `cadastrar_artigo`, `editar_analise`, `minhas_analises`,
  `submeter_analise`, `buscar_artigo` + parciais `_preview_metadados`,
  `_card_analise`, `_busca_resultados`
- [x] Cobertura `apps/acervo` em 93%; suite com 355 passed, 1 xfailed,
  0 failed

---

## Pendências acumuladas para o usuário

Itens não-bloqueantes deixados nas fases concluídas. Reúno aqui pra
ficar visível antes do deploy de produção.

### Da Fase 0
- [ ] Criar repositório no GitHub (ou outro provider) e adicionar como
  remote — ativa o CI versionado em `.github/workflows/ci.yml`
- [ ] Uniformizar ownership do diretório (`chown -R anco-paulovicente:anco-paulovicente .`)
- [ ] Definir nome próprio da plataforma (spec §15.2)

### Da Fase 1
- [ ] Revisar a fixture `apps/vocabulario/fixtures/vocabularios_iniciais.json`
- [ ] Revisar os ~290 termos `ativo=False` criados pela importação real
  do legado em `/admin/vocabulario/termovocabulario/?ativo__exact=0`
- [ ] Decidir política de fusão de analistas legado (81 users com
  variantes de capitalização)

### Da Fase 2
- [ ] Criar credenciais OAuth no Google Cloud Console e injetar no `.env`
  (`GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_CLIENT_SECRET`)
- [ ] Atualizar `Site` (id=1) no admin para o domínio real
- [ ] Definir `DEFAULT_FROM_EMAIL` no `.env`
- [ ] Promover seu próprio usuário a curador após primeiro login OAuth
