# Roadmap — Plataforma AnCo

> **Status vivo do roadmap**. Cada item dos critérios de aceite aqui é
> um espelho do escopo definido em [`ESPECIFICACAO.md` §10](ESPECIFICACAO.md);
> em conflito, a especificação prevalece.
>
> Cada fase concluída tem relatório detalhado em [`relatorios/`](relatorios/).

**Status atual**: Fase 4 concluída — aguardando aprovação para iniciar a Fase 5.

| # | Fase | Estimativa | Status | Relatório |
|---|------|-----------|--------|-----------|
| 0 | Fundação | 1 dia | ✅ concluída | [fase-0.md](relatorios/fase-0.md) |
| 1 | Núcleo de dados e admin | 2-3 dias | ✅ concluída | [fase-1.md](relatorios/fase-1.md) |
| 2 | Autenticação e cadastro | 1-2 dias | ✅ concluída | [fase-2.md](relatorios/fase-2.md) |
| 3 | Criação e edição de análises | 3-4 dias | ✅ concluída | [fase-3.md](relatorios/fase-3.md) |
| 4 | Revisão por pares | 3-4 dias | ✅ concluída | [fase-4.md](relatorios/fase-4.md) |
| 5 | Acervo público | 3-4 dias | ⬜ pendente | — |
| 6 | API, métricas e saúde de links | 2-3 dias | ⬜ pendente | — |
| 7 | Polimento e produção | 2 dias | ⬜ pendente | — |
| 8 | Busca semântica | 3-4 dias | ⬜ pendente | — |

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

## Fase 5 — Acervo público ⬜

- [ ] Listagem `/acervo/` com paginação (20/página)
- [ ] Busca facetada (Postgres FTS + facetas dinâmicas)
- [ ] Página do artigo (`/artigo/<doi-slug>/`)
- [ ] Página da análise (`/analise/<id>/`)
- [ ] Selo de destaque para resenhas críticas peer-reviewed
- [ ] Histórico de versões consultável (diff)
- [ ] Geração de citação ABNT/APA
- [ ] Selo CC-BY-NC visível no rodapé das análises
- [ ] **URLs estáveis e citáveis desde o dia 1** (bloqueia mudanças
  retroativas)
- [ ] **Aceite**: navegar, buscar e citar análises sem login

## Fase 6 — API, métricas e saúde de links ⬜

- [ ] API REST somente-leitura (`/api/v1/`) via DRF
- [ ] Documentação Swagger via `drf-spectacular` (`/api/docs`)
- [ ] Filtros equivalentes às facetas
- [ ] Tarefa periódica (semanal) de verificação de links (HEAD)
- [ ] Tela curador "Links quebrados" com promoção do snapshot Wayback
- [ ] Dashboard administrativo (status, fila de revisão, cobertura,
  links quebrados)
- [ ] Validação anti-SSRF na verificação de links

## Fase 7 — Polimento e produção ⬜

- [ ] Caddy 2 no compose com Let's Encrypt automático
- [ ] Backup `pg_dump` diário + sincronia S3-compatible
- [ ] `RESTORE.md` documentando teste de restore (trimestral em staging)
- [ ] Logs estruturados
- [ ] Monitoring (Sentry self-hosted ou GlitchTip)
- [ ] Páginas estáticas: Sobre, Equipe, Termos de Uso, Política de
  Privacidade
- [ ] Rate limiting em busca e API (`django-ratelimit`)
- [ ] CSP restritiva
- [ ] Deploy em produção
- [ ] Plano de redirecionamento permanente do domínio temporário

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
