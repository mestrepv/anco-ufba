# Relatório — Fase 3: Criação e edição de análises

**Data**: 2026-04-29
**Branch**: `fase-3-criacao-analises` (a partir de `fase-2-auth-cadastro`)
**Commits**: 5 atômicos por área

## O que foi entregue

### Frontend ativado: Tailwind + HTMX + Alpine via CDN

- `_base.html` redesenhado: layout responsivo (`max-w-5xl`), header com
  navegação contextual (links variam por papel), footer com licença
  CC-BY-NC, paleta `anco` (azul institucional `#144d77`), fonte
  `system-ui`, mensagens estilizadas por nível.
- Tailwind via CDN (`cdn.tailwindcss.com`) — sem pipeline de build nesta
  fase. Pipeline com purge fica para Fase 7 se a performance pedir.
- HTMX 2.0.4 e Alpine.js 3.14.7 via `unpkg`.

### Serviços de link e Wayback Machine ([apps/acervo/services/links.py](apps/acervo/services/links.py))

- `LinkCheckResultado` (dataclass): status, código HTTP, URL final, mensagem.
- `_eh_url_publica`: anti-SSRF rejeitando IPs privados, loopback,
  link-local e reservados.
- `validar_link(url)`: HEAD com timeout 8s, fallback para GET stream em
  405, classifica `ok`/`redireciona`/`quebrado`. Erros de rede caem em
  `quebrado` com mensagem.
- `aplicar_resultado_no_artigo`: persiste `link_status` +
  `link_ultima_verificacao`.
- `capturar_snapshot_wayback`: chama `https://web.archive.org/save/<url>`,
  cria `SnapshotLink`. Gateado por `settings.WAYBACK_API_ENABLED`.
  Timeout 30s. Falhas log warning + return None — nunca bloqueia o usuário.

### Forms multipasso ([apps/acervo/forms.py](apps/acervo/forms.py))

- `BuscaArtigoForm`: campo livre.
- `ArtigoForm`: cadastro novo artigo, `link_acesso` e `base_consulta`
  obrigatórios (conforme spec §5.2).
- `AnalisePresencaForm`, `AnaliseEstruturaForm`, `AnaliseResenhaForm`:
  forms parciais por passo do multipasso.
- `AnaliseCompletaForm`: aceita qualquer subset (usado pelo auto-save).
- Todos os widgets têm classes Tailwind aplicadas no `__init__`.

### Views ([apps/acervo/views.py](apps/acervo/views.py))

Todas com decorator `_exige_analista` (anonimo → login, leitor → 403):

- `minhas_analises_view`: lista as próprias análises ordenadas por data,
  com badges de status coloridos.
- `buscar_artigo_view`: busca por DOI/título/autor; resposta varia
  conforme `HX-Request` (página completa vs partial HTMX).
- `cadastrar_artigo_view`: cria `Artigo`, valida o link, cria `Analise`
  vinculada ao analista corrente.
- `capturar_snapshot_view`: aciona Wayback (POST + retorna partial HTMX
  com resultado).
- `iniciar_analise_view`: cria/recupera `Analise` para um Artigo
  existente — idempotente.
- `editar_analise_view`: multipasso (`?passo=identificacao|presenca|estrutura|resenha`)
  com avanço automático após POST válido.
- `autosave_analise_view`: aceita POST com qualquer subset, retorna JSON
  `{ok, salvo_em}`; recusa se análise não for rascunho ou se outro user.
- `submeter_analise_view`: rascunho → submetida + `submetida_em`;
  mensagem diferenciada quando `tem_resenha=True` (avisa sobre revisão
  cega adicional na Fase 4).

### Templates ([templates/acervo/](templates/acervo/))

- `minhas_analises.html`: tabela com badges de status.
- `buscar_artigo.html` + `_busca_resultados.html`: busca incremental via
  HTMX (`hx-trigger="keyup changed delay:400ms"`).
- `cadastrar_artigo.html`: form com indicação de obrigatórios.
- `_snapshot_resultado.html`: partial HTMX para resultado Wayback.
- `editar_analise.html`: stepper de 4 passos; **auto-save via Alpine.js**
  (`setInterval(30000)` chamando `autosave_analise`); contador "Auto-salvo
  às HH:MM:SS"; aviso especial no passo resenha; botão de submissão no
  passo final.
- `submeter_analise.html`: confirmação com aviso sobre revisão cega
  adicional quando `tem_resenha`.

## Critério de aceite (spec §10 — Fase 3)

- [x] Busca/criação de Artigo com validação de link (HEAD)
- [x] Integração Wayback Machine (botão "Capturar snapshot")
- [x] Formulário multipasso com HTMX (4 passos)
- [x] Quarto passo opcional: Resenha Crítica
- [x] Auto-save a cada 30s
- [x] Submissão para revisão (rascunho → submetida)
- [x] Tailwind + Alpine.js entram nesta fase
- [x] **Aceite formal**: criar análise completa do zero, com e sem resenha
  — confirmado em testes (24 cenários novos) e shell manual end-to-end
  (`tem_resenha` flipa, status muda, histórico grava 5 versões)

## Decisões tomadas

- **Tailwind via CDN** em vez de pipeline npm: economia de complexidade
  (sem container Node, sem npm install no build). CDN funciona offline
  no dev se o usuário cachear; em prod, troca por bundle se a equipe
  pedir.
- **Auto-save no client**, não no Django: setInterval no Alpine.js +
  endpoint dedicado JSON. Mais previsível que `hx-trigger` em todos os
  campos. Endpoint aceita subset para tolerar diferenças entre passos.
- **Decorator `_exige_analista`** em vez de classe-based view: stack mais
  simples para 8 views; pode virar `LoginRequiredMixin + UserPassesTest`
  quando virar muito.
- **`autosave` recusa análises não-rascunho**: evita corromper análises
  já submetidas se o usuário deixar uma aba antiga aberta.
- **Snapshot retorna `legacy:*` quando IA não dá header explícito**: o
  redirect funcional do Wayback resolve a versão mais recente — é
  imperfeito mas funciona.
- **Iniciar análise é idempotente** (`get_or_create`): clique repetido
  não duplica.
- **Validação de link é fire-and-forget no cadastro**: erro silencioso
  para não bloquear cadastro se o IA estiver fora.
- **Alpine via `x-data` inline em vez de componente externo**: a única
  lógica é o auto-save; importar Alpine só para isso já é suficiente.
- **Não há rota pública "ver análise"** ainda — isso é Fase 5 (acervo
  público).

## Desvios da especificação

- **Sem auto-criação de signal de sorteio**: spec §5.2 termina dizendo
  que submeter "dispara sorteio". Sorteio é Fase 4 — aqui apenas mudo
  `status` e seto `submetida_em`. Mensagem para o usuário menciona
  revisão futura.
- **Search incremental usa `keyup changed delay:400ms`** (HTMX):
  spec não dita o delay. 400ms é confortável.
- **Sem busca facetada na criação**: spec §6.2 fala em facetas, mas
  isso é da Fase 5 (acervo público). Aqui a busca é simples (`icontains`
  em título/autores + `iexact` em DOI).

## Dívida técnica deixada

- **Sem CSP de Tailwind/CDN**: scripts inline + CDN passam pelo CSP
  básico atual (que é permissivo em dev). Em prod, será preciso ajustar
  CSP para permitir os domínios `cdn.tailwindcss.com` e `unpkg.com`, ou
  bundlar localmente.
- **Falta indicador visual de "auto-save em andamento"**: hoje só
  aparece quando `ultimoSave` é setado. Uma versão "salvando..." seria
  mais clara.
- **Sem confirmação de saída com alterações não salvas**: se o usuário
  fechar a aba antes do próximo auto-save (até 30s), perde até 30s.
  `beforeunload` listener resolve.
- **Sem upload de avatar nem rich text editor**: resenha é textarea
  pura. Markdown rendering vai para Fase 5.
- **Validação de link na cadastrar é síncrona**: bloqueia o request por
  até 8s no pior caso. Em produção real, mover para task assíncrona
  django-q2.
- **Snapshot Wayback é síncrono**: idem — mover para task assíncrona
  na Fase 4 (que já vai ter worker).

## Métricas

- **Cobertura**: 93% (1.076 statements, 80 misses).
- **Testes**: 158 (35 novos: 11 services + 24 views Fase 3).
- **Linhas adicionadas**: ~1.250 (templates, serviços, forms, views, testes).
- **Arquivos criados**: 13 (4 templates, services.py, forms.py, views.py,
  urls.py acervo, tests, partials HTMX, snapshot template).
- **Tempo aproximado da fase**: ~1h.

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 4:

1. **Testar OAuth real com Google**: Fase 2 deixou pendente a criação
  do cliente OAuth no Google Cloud Console. Para validar a Fase 3
  com user real (não shell), o login OAuth precisa funcionar. Em dev
  local, alternativa é usar `force_login` via shell.
2. **Revisar o vocabulário ativo**: o cadastro de novo artigo só lista
  termos `ativo=True` em `base_consulta`. A migração da Fase 1 deixou
  vários inativos para curadoria.
3. **Ajustar CSP do Caddy** quando entrar (Fase 7) para liberar os CDNs
  de Tailwind/HTMX/Alpine — ou bundlar localmente nessa hora.

**Aprovação para iniciar a Fase 4** (Revisão por pares: sorteio
automático com worker django-q2, mascaramento de autoria nas cegas,
formulário de revisão, lógica de transição de status) é o próximo passo.
