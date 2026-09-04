# Relatório — Fase 7: Polimento e produção

**Data**: 2026-04-29
**Branch**: `fase-7-producao` (a partir de `fase-6-saude-links-dashboard`)
**Commits**: 5 atômicos por área

Última fase pré-deploy. Endurece a plataforma para produção e
documenta o procedimento de deploy/restore. **A entrega não inclui o
deploy real** (depende do domínio, credenciais Google OAuth,
infraestrutura S3) — apenas tudo que é necessário para que o deploy
seja executável conforme o `docs/operacao/DEPLOY.md`.

## O que foi entregue

### Caddy 2 + HTTPS automático ([infra/Caddyfile](infra/Caddyfile))

- Reverse proxy com Let's Encrypt automático (e-mail e domínio via env).
- Headers de segurança: HSTS 1 ano, X-Content-Type-Options, X-Frame-Options
  DENY, Referrer-Policy same-origin, header `Server` removido.
- Compressão gzip+zstd, static files servidos diretamente do disco
  (mais rápido que via gunicorn).
- Logs JSON em stdout.
- Container `caddy` no compose sob profile `prod` — só sobe com
  `--profile prod`; em dev acessa direto via `:8000`.

### Backup pg_dump ([apps/core/management/commands/backup_db.py](apps/core/management/commands/backup_db.py))

- `manage.py backup_db [--output DIR] [--retencao-dias N] [--no-prune]`
- Custom format compactado, nome timestamped UTC, retenção configurável.
- Senha via `PGPASSWORD` (não na linha de comando).
- Falha bonita se `pg_dump` ausente ou erro do subprocess.
- `Dockerfile` agora inclui `postgresql-client`.
- Script wrapper `infra/backup/run.sh` para cron do host: roda o
  backup + sincroniza com S3-compatible se configurado.

### Logs estruturados, CSP, Sentry, rate limit ([config/settings/prod.py](config/settings/prod.py))

- **Logs JSON**: `_JsonFormatter` próprio (sem dep externa) serializa
  todos os atributos de `LogRecord` em JSON compacto na stdout. Pronto
  para Loki/Vector/etc.
- **CSP** via `django-csp`:
  - `default-src 'self'`
  - `script-src` com Tailwind/HTMX/Alpine CDNs (herança da Fase 3 — bundlar
    local em v2)
  - `frame-ancestors 'none'`, `form-action 'self'`, `object-src 'none'`
- **Sentry SDK** opcional (DSN via `SENTRY_DSN`; vazio = no-op):
  DjangoIntegration + LoggingIntegration capturando ERROR+, sem PII,
  `traces_sample_rate` configurável.
- **CSRF_TRUSTED_ORIGINS** auto-gerado a partir de `ALLOWED_HOSTS`
  (necessário para forms cross-site no allauth).
- **Rate limiting** via allauth `ACCOUNT_RATE_LIMITS` em `base.py`:
  5 falhas/5min, 30 logins/5min, 3 signups/h, 5 emails/h.
- **Rate limiting da listagem pública** com `@ratelimit(key="ip",
  rate="60/m", block=False)` — soft limit que marca `request.limited`.

### Páginas institucionais ([templates/publico/](templates/publico/))

4 páginas estáticas em `/sobre/`, `/equipe/`, `/termos/`,
`/privacidade/`, com conteúdo preliminar:
- **Sobre**: princípios, escopo, licença
- **Equipe**: contato, domínios institucionais aceitos
- **Termos de uso**: 9 seções (aceitação, quem pode usar, conteúdo,
  obras, revisão, permanência, limitações, mudanças, contato) com CC-BY-NC
- **Privacidade**: 8 seções aderentes a LGPD básica (dados coletados,
  finalidade, cookies, compartilhamento, retenção, direitos, segurança,
  contato)

Footer do `_base.html` linka para as 4. Todos os textos marcados como
"versão preliminar — em revisão".

### SEO: robots.txt e sitemap.xml

- `/robots.txt` com `Disallow` em `/admin/`, `/accounts/`, `/cadastro/`,
  `/acervo-analista/`, e link para o sitemap.
- `/sitemap.xml` listando: home, `/acervo/`, páginas institucionais,
  todas as análises publicadas/legado, e artigos cuja análise é
  pública (com `lastmod`). No estado atual, **8.204 linhas / 1.095
  análises listadas**.

### Documentação

- **[docs/operacao/DEPLOY.md](docs/operacao/DEPLOY.md)**: 9 seções cobrindo pré-requisitos
  do servidor, configuração inicial completa (env, profiles, migrate,
  collectstatic, fixtures, schedules, OAuth, Site, migrate_legacy),
  atualização contínua, backup automatizado via cron do host, logs e
  observabilidade, healthcheck, plano de redirecionamento (spec §9.3),
  modo manutenção, rollback.
- **[docs/operacao/RESTORE.md](docs/operacao/RESTORE.md)**: procedimento staging e prod,
  checklist pós-restore, **roteiro de teste trimestral** (sem o qual
  o backup é "wishful thinking"), troubleshooting.

## Critério de aceite (spec §10 Fase 7)

- [x] Caddy 2 no compose com Let's Encrypt automático
- [x] Backup `pg_dump` diário (script + comando) + sincronia
  S3-compatible (gateado por env)
- [x] `RESTORE.md` documentando teste de restore (trimestral em staging)
- [x] Logs estruturados (JSON formatter próprio em prod)
- [x] Monitoring básico (Sentry SDK opcional via DSN)
- [x] Páginas estáticas: Sobre, Equipe, Termos de Uso, Política de Privacidade
- [x] Rate limiting em busca e login (`django-ratelimit` + `ACCOUNT_RATE_LIMITS`)
- [x] CSP restritiva (`django-csp` em prod)
- [x] Plano de redirecionamento permanente (documentado em DEPLOY.md §7)
- [⏳] **Deploy em produção**: documentado e pronto, mas o deploy real
  depende de credenciais OAuth Google, domínio com DNS apontado e
  acesso S3 — fora do controle do agente.

## Decisões tomadas

- **Caddy sob profile `prod`** em vez de default: desenvolvimento
  iterativo continua sem TLS local. Em prod, `--profile prod` ativa.
- **Tailwind/HTMX/Alpine via CDN no CSP**: a Fase 3 escolheu CDN; a
  CSP teve que abrir `cdn.tailwindcss.com` e `unpkg.com`. Bundlar
  localmente apertaria a CSP — adiável para v2.
- **`_JsonFormatter` próprio em vez de `python-json-logger`**: ~30
  linhas, sem dependência. Serializa todos os atributos do `LogRecord`,
  inclusive os custom passados via `extra={...}`.
- **Sentry com DSN opcional**: se vazio, `sentry_sdk.init` nem é
  chamado. Permite rodar prod sem Sentry e ligar depois.
- **Rate limit da listagem em `block=False`**: marca `request.limited`
  para análise de tráfego, mas não devolve 429. Em volume real podemos
  endurecer; soft é mais seguro pra começar (não bloqueia legítimos).
- **Páginas institucionais como templates simples**, não Flatpages:
  evita migration extra; mais fácil de versionar em git; suficiente
  para conteúdo curatorial estático.
- **`PGPASSWORD` via env, não argumento**: `pg_dump` aceita
  `--password` mas isso vaza no `ps`. Env é seguro (limitado ao
  processo).
- **Sitemap calculado on-the-fly**, sem cache: ~1.000 URLs renderiza
  rápido. Em escala maior, cachear.
- **`ANCO_DOMAIN` e `ANCO_ADMIN_EMAIL`** como variáveis dedicadas no
  Caddyfile: separa do `BASE_URL` (que é da view do Django) — Caddy
  precisa do hostname puro sem esquema.
- **Reverse-proxy log do Caddy em JSON**: combina com o resto do
  pipeline de logs.

## Desvios da especificação

- **Deploy em produção não executado**: depende de recursos externos
  (domínio, OAuth credentials, S3). Documentação cobre tudo que falta.
- **Sentry self-hosted (GlitchTip)** não foi instalado — só o cliente
  SDK é integrado. Auto-hospedar GlitchTip é trabalho separado de infra
  documentado em DEPLOY.md como opcional.
- **CSP libera CDNs**: spec §13 exige "CSP restritiva". A CSP é
  restritiva mas não fechada — abre Tailwind/HTMX/Alpine. Documentado
  como dívida.

## Dívida técnica deixada

- **Bundlar Tailwind/HTMX/Alpine localmente** apertaria a CSP. Adiável
  para v2 quando houver pipeline npm/esbuild.
- **Sitemap sem cache**: 1.000 URLs hoje; quando passar de ~10k, vai
  doer. Usar `Cache-Control: public, max-age=3600` no header é fix
  simples.
- **Páginas institucionais sem editor para curadores**: mudanças exigem
  PR. Aceitável para conteúdo institucional estável; se virar dor,
  trocar por flatpages.
- **Backup S3 não testa autenticação no script**: silently pula se
  awscli não está instalado. Em produção real, falha alta seria
  preferível — mas a `awscli` deve estar no ambiente do cron host.
- **CSP em `report-only` não configurado**: caso a CSP esteja apertada
  demais para algum browser/extensão, browsers só silenciam o erro.
  Adicionar `CSP_REPORT_URI` e endpoint receptor em produção real.
- **Sem teste real do Caddy**: `docker compose --profile prod up` exige
  domínio público para Let's Encrypt funcionar. Em dev local, `local_certs`
  comentado no Caddyfile permite testar com cert auto-assinado.

## Métricas

- **Cobertura**: 92% (1.768 statements, 144 misses).
- **Testes**: **263** (15 novos: 12 institucional/SEO + 3 backup).
- **Linhas adicionadas**: ~1.060 (settings prod, backup command, 4
  páginas institucionais, schema views, Caddyfile, scripts, 2 docs
  longos).
- **Arquivos criados**: 13.
- **Tempo aproximado**: ~1h.

## Pendências para o usuário

**Críticas para o deploy real**:

1. **Provisionar servidor de produção** (Ubuntu 22.04 + Docker; 2GB+ RAM).
2. **Apontar DNS** do domínio (`anco.paulovicente.pro.br` ou
   institucional) para o IP do servidor.
3. **Liberar portas 80 e 443** (firewall/security group) para Let's
   Encrypt obter cert.
4. **Criar credenciais OAuth Google** no Cloud Console (callback URL
   apontando para o domínio definitivo).
5. **Provisionar S3-compatible** (MinIO self-hosted, Wasabi, R2,
   Backblaze B2) e configurar `BACKUP_S3_*`.
6. **Configurar `SENTRY_DSN`** se for usar Sentry/GlitchTip.

**Pós-deploy**:

7. **Rodar primeira execução** do `setup_q_schedules` (ativa cron de
   verificação de prazos e links).
8. **Cron do host**: agendar `infra/backup/run.sh` diário às 03:00.
9. **Teste de restore em staging**: dentro de 90 dias do go-live, fazer
   o primeiro teste trimestral (RESTORE.md §5).
10. **Revisar conteúdo institucional**: textos de Termos e Privacidade
    estão como "versão preliminar — em revisão". Idealmente revisão
    jurídica antes de tráfego real.

## Roadmap concluído

Com a Fase 7, **todas as 8 fases base do roadmap (0-7) estão concluídas**.
A Fase 8 (busca semântica) permanece como adendo opcional v2.1, a ser
implementada após a plataforma estar em produção e com volume real
de análises.

Resumo do que foi construído ao longo das 8 fases:

| Fase | Entrega-chave | Coverage final |
|---|---|---|
| 0 | Fundação (Django, Compose, CI) | 100% |
| 1 | 9 modelos + admin + migrate_legacy (1.443 registros) | 96% |
| 2 | Auth Google OAuth + cadastro institucional + signal | 94% |
| 3 | Criação de análises (multipasso HTMX + auto-save + Wayback) | 93% |
| 4 | Revisão por pares (sorteio, mascaramento, transição automática) | 92% |
| 5 | Acervo público (FTS, facetas, citação ABNT/APA, CC-BY-NC) | 91% |
| 6 | Saúde de links + dashboard + JSON-LD (v2.2 escopo) | 92% |
| 7 | Caddy + backup + CSP + Sentry + páginas institucionais | 92% |

**263 testes passando, 92% cobertura, 1.768 statements, 8 fases completas.**
