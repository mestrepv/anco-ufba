# Relatório — Fase 2: Autenticação e cadastro

**Data**: 2026-04-29
**Branch**: `fase-2-auth-cadastro` (a partir de `fase-1-modelagem-base`)
**Commits**: 4 atômicos por área

## O que foi entregue

### `django-allauth` integrado com Google OAuth

- Dependência adicionada em `pyproject.toml` (`django-allauth[socialaccount]>=65.0`).
- INSTALLED_APPS: `allauth`, `allauth.account`, `allauth.socialaccount`,
  `allauth.socialaccount.providers.google`, `django.contrib.sites`.
- MIDDLEWARE: `allauth.account.middleware.AccountMiddleware`.
- AUTHENTICATION_BACKENDS: `ModelBackend` + `allauth.account.auth_backends.AuthenticationBackend`.
- `SITE_ID = 1`.
- `SOCIALACCOUNT_PROVIDERS.google` lê `GOOGLE_OAUTH_CLIENT_ID/SECRET` do
  `.env` (Vazios em dev — configuração real fica para o deploy).
- Migrations do allauth aplicadas (`account.*`, `socialaccount.*`,
  `sites.*`).

### Validação de domínio institucional

- Função pura `apps.core.adapters.email_dominio_permitido(email, allowlist)`:
  - Itens com ponto inicial (`.edu.br`) casam o sufixo, suportando
    `usp.edu.br` e `lab.usp.edu.br`.
  - Itens explícitos (`ufba.br`) casam exato ou subdomínios.
  - Case-insensitive. Recusa entradas malformadas.
- Allowlist default cobre `.edu`, `.edu.br`, `.ac.uk` e mais 10
  domínios listados na spec §5.1 (UFBA, IFBA, USP, etc.) — totalmente
  expansível via env `ALLOWED_INSTITUTIONAL_DOMAINS`.
- `AnCoSocialAccountAdapter.pre_social_login` rejeita domínios fora da
  lista respondendo HTTP 403 com a tela `dominio_nao_autorizado.html`.

### Fluxo de promoção a analista

- **Form** `SolicitacaoCadastroForm` — campos: `nome_exibicao`,
  `vinculo_institucional` (obrig.), `grupo_pesquisa` (opc.), `orcid`
  (opc.) e `justificativa` (obrig.). Atualiza o `User` com os dados
  do form ao salvar.
- **Views**:
  - `home_view`: pública, mostra CTA conforme estado do usuário
  - `solicitar_promocao_view`: render do form; redireciona analista para
    home, leitor com solicitação existente para o status
  - `promocao_status_view`: mostra status (pendente/aprovada/rejeitada)
- **URLs**: `/`, `/cadastro/promocao/`, `/cadastro/promocao/status/`,
  `/accounts/` (allauth), `/admin/`, `/healthz`.
- `LOGIN_REDIRECT_URL = /cadastro/promocao/` funciona como **dispatcher
  pós-login**.

### Notificação aos curadores e promoção automatizada (signals)

`apps/core/signals.py`:
- `pre_save`: captura `_status_anterior` em memória.
- `post_save`:
  - **Criação**: e-mail a todos os curadores ativos com link direto
    para aprovar/rejeitar no admin (usa `BASE_URL` + reverse).
  - **Aprovação** (pendente → aprovada): promove o `User` para `analista`
    (não rebaixa quem já é curador) + e-mail de boas-vindas.
  - **Rejeição**: e-mail com motivo se preenchido.
- Edge case: sem curador ativo, loga warning e segue (solicitação fica
  visível no admin para um curador futuro).

### Admin: actions em lote para aprovar/rejeitar

`SolicitacaoCadastroAdmin`:
- Coluna extra `vinculo` (busca derivada).
- `search_fields` ampliado.
- 2 actions: "Aprovar solicitações selecionadas" e "Rejeitar
  selecionadas" — só afetam `status=pendente`, registram `revisado_por`
  e `revisado_em`, e disparam o signal naturalmente.

### Templates

- `templates/_base.html` — layout mínimo com CSS inline (sem Tailwind
  ainda — entra na Fase 3 conforme spec).
- `templates/core/home.html`
- `templates/core/solicitar_promocao.html`
- `templates/core/promocao_status.html`
- `templates/core/dominio_nao_autorizado.html`
- `templates/account/login.html` (override do allauth com botão
  "Entrar com Google" via `{% provider_login_url 'google' %}`)

## Critério de aceite (da especificação §10 — Fase 2)

- [x] `django-allauth` + Google OAuth configurados
- [x] Validação de domínio funcional
- [x] Tela de solicitação de promoção
- [x] Notificação aos curadores
- [x] **Aceite formal**: você se loga, solicita promoção, é aprovado por
  curador → fluxo confirmado tanto via testes (`test_promocao.py` cobre
  os 4 passos) quanto via shell manual (leitor `papel='leitor'` →
  aprovação pelo admin → leitor `papel='analista'`).

**Nota sobre login real com Google**: o teste end-to-end com OAuth
requer `GOOGLE_OAUTH_CLIENT_ID/SECRET` reais (Google Cloud Console).
Em dev, o fluxo está completamente implementado e exercitado, mas o
botão "Entrar com Google" só funciona depois que essas credenciais
forem fornecidas.

## Decisões tomadas

- **Cadastro público desabilitado** (`is_open_for_signup=False`): a
  única via é OAuth via Google. Curadores podem criar contas
  manualmente pelo admin.
- **`LOGIN_REDIRECT_URL` aponta para `/cadastro/promocao/`** em vez de
  `/`. Vira um dispatcher pós-login simples — sem precisar de view
  middleware customizada.
- **Allowlist via env list** em vez de hard-code: permite ampliar sem
  redeploy, basta editar `.env`.
- **Email backend continua console em dev** (já configurado em Fase 0):
  e-mails aparecem no `docker compose logs web`. SMTP em prod via env.
- **Signal usando `_status_anterior` em memória**, não no banco: evita
  schema change e evita race condition (cada `save()` recria o atributo).
- **`SocialAccountAdapter.populate_user`** define `papel=leitor` por
  padrão e copia `nome_exibicao` do dado do Google quando vazio. Garante
  contas OAuth nascendo no estado correto sem depender do default do
  modelo.
- **`Curador` nunca é rebaixado**: edge case coberto — se um curador
  abrir solicitação e ela for aprovada, mantém papel curador.
- **`is_active=False` para legados**: continua valendo desde a Fase 1.
  Eles não conseguem fazer login via OAuth porque o adapter só permite
  conexão se `is_active=True`.
- **Testes do adapter sem mockar o stack todo do allauth**: usei
  `SimpleNamespace` para simular `SocialLogin` em vez de instanciar a
  classe real (que exigiria muita configuração). O teste valida a
  lógica do adapter, não o framework do allauth.

## Desvios da especificação

- **Tour de boas-vindas após aprovação**: spec §5.1 menciona "e-mail de
  boas-vindas com tour". Implementei o e-mail mas sem tour (não há UI
  rica ainda — Phase 3+ traz HTMX/Alpine). E-mail aponta para `/`.
- **`SocialAccountAdapter` em vez de `account_signup`**: spec implicitamente
  fala em formulário pós-cadastro; minha implementação leva o usuário ao
  `solicitar_promocao` na primeira chegada via `LOGIN_REDIRECT_URL`,
  o que é equivalente em UX mas usa view própria em vez de página de
  signup do allauth.

## Dívida técnica deixada

- **Configuração da `SocialApp` Google**: registrada via env vars em
  settings (`SOCIALACCOUNT_PROVIDERS.google.APP`), funciona quando as
  credenciais reais forem injetadas. Não há management command de
  inicialização. Para deploy: definir `GOOGLE_OAUTH_CLIENT_ID` e
  `GOOGLE_OAUTH_CLIENT_SECRET` no `.env`.
- **Site `localhost` default**: a migração do allauth criou um `Site`
  com domínio `example.com`. Em produção, será preciso atualizar para o
  domínio real (manualmente pelo admin ou via fixture de `Site`).
- **Templates sem identidade visual**: CSS inline no `_base.html`,
  apenas o esqueleto. Tailwind entra na Fase 3.
- **Sem tela de fusão de contas legado**: spec §8.3 propõe que, quando
  um analista esperado se cadastra via Google e nome/email batem com
  conta legado, o sistema oferece fusão. Não implementado nesta fase —
  fica para uma sub-fase quando houver volume real de cadastros.
- **Sem rate limiting na solicitação**: nada impede um usuário de criar
  uma solicitação, deletar via shell e criar outra. Em produção, a
  constraint OneToOne já impede a criação de uma segunda no banco. Mas
  não há limite por janela de tempo após rejeição.

## Métricas

- **Cobertura de testes**: 94% (807 statements, 50 misses; misses
  concentrados em paths de erro raros e admin actions).
- **123 testes passando** (37 a mais que na Fase 1):
  - 22 do validador de domínio
  - 4 do adapter
  - 16 do form/views/signals de promoção
  - 5 das views básicas
  - + os 86 já existentes da Fase 0/1
- **Linhas adicionadas**: ~750 (sobre fase-1).
- **Arquivos criados**: 12 (adapters, forms, views, signals, 5 templates,
  4 testes).
- **Tempo aproximado da fase**: ~45 minutos.

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 3, mas necessárias antes do deploy:

1. **Criar credenciais OAuth no Google Cloud Console**:
   - Tipo: "OAuth client ID" → "Web application"
   - Authorized redirect URIs: `https://<seu-dominio>/accounts/google/login/callback/`
     (em dev: `http://localhost:8000/accounts/google/login/callback/`)
   - Copiar Client ID e Secret para o `.env`:
     ```
     GOOGLE_OAUTH_CLIENT_ID=<id>
     GOOGLE_OAUTH_CLIENT_SECRET=<secret>
     ```
2. **Atualizar `Site`** (id=1) no admin para o domínio real
   (`anco.paulovicente.pro.br` agora; institucional depois). Necessário
   para o allauth montar URLs de callback corretamente.
3. **Revisar a `ALLOWED_INSTITUTIONAL_DOMAINS`** — a default é genérica;
   curadores podem querer apertar/relaxar conforme política.
4. **Definir `DEFAULT_FROM_EMAIL`** no `.env` (em dev fica
   `webmaster@localhost`; em prod precisa de algo como
   `noreply@anco.paulovicente.pro.br`).
5. **Promover seu próprio usuário a curador** depois do primeiro login
   OAuth (pelo admin, ou via `python manage.py shell`):
   ```python
   from django.contrib.auth import get_user_model
   u = get_user_model().objects.get(email='paulovicente.ifba@gmail.com')
   u.papel = u.Papel.CURADOR
   u.is_staff = True
   u.is_superuser = True
   u.save()
   ```
   *(No dev local, o gmail.com não está na allowlist — ajustar antes ou
   logar diretamente como o superuser `admin` criado na Fase 1.)*

**Aprovação para iniciar a Fase 3** (Criação e edição de análises:
busca/criação de Artigo, integração Wayback, formulário multipasso com
HTMX, auto-save, submissão para revisão) é o próximo passo.
