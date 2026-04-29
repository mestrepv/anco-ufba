# Relatório — Fase 4: Revisão por pares

**Data**: 2026-04-29
**Branch**: `fase-4-revisao-pares` (a partir de `fase-3-criacao-analises`)
**Commits**: 5 atômicos por área

A fase de lógica de domínio mais densa do projeto. Desde o início,
seguindo CLAUDE.md §9.2, escrevi os testes do fluxo completo cobrindo
**os 7 cenários obrigatórios** explicitados ali.

## O que foi entregue

### Worker django-q2 ([infra/docker-compose.yml](infra/docker-compose.yml))

- Container `worker` (mesmo Dockerfile, comando `manage.py qcluster`)
  sob profile `worker`. Em dev, opt-in via `--profile worker`. Em prod
  será default.
- `Q_CLUSTER` em [config/settings/base.py](config/settings/base.py):
  broker Redis (db=1), workers=2, timeout=60s, retry=90s.
- `dev.py` força `sync=True` — tasks rodam no próprio processo do web
  (e nos testes). Iteração rápida sem precisar do worker.

### Serviço de sorteio ([apps/acervo/sorteio.py](apps/acervo/sorteio.py))

- `revisores_elegiveis(analise, excluir_ids)`: queryset que aplica
  **todas as exclusões da spec** §5.3:
  - Papel ∈ {analista, curador}, `is_active=True`, `aceita_revisoes=True`
  - `revisoes_pendentes < limite_revisoes_simultaneas` (annotate + F)
  - **Não é o autor da análise**
  - **Não tem outra análise do mesmo artigo** (preserva independência
    entre múltiplas análises do mesmo artigo)
  - Não está em `excluir_ids` (revisores já sorteados na passada atual)
- `executar_sorteio(analise)`:
  1. Idempotente (skip se já há revisões)
  2. 2 estruturais → se faltar, **fila de espera sem persistir parciais**
  3. Se `tem_resenha`: +2 cegos distintos dos estruturais → idem
  4. Persiste com prazo +14 dias (estrutural) ou +21 dias (cega)
  5. `submetida → em_revisao`
- `re_sortear_revisao_expirada(revisao)`: substitui revisor + estende
  prazo. Retorna None se sem substituto.
- `revisoes_expiradas()`: queryset para o cron diário.

### Serviço de aprovação ([apps/acervo/aprovacao.py](apps/acervo/aprovacao.py))

`avaliar_apos_revisao(analise)`:
1. Só decide se status==`em_revisao`
2. Só decide se TODAS as revisões estão concluídas
3. Algum `REJEITAR` → volta para `rascunho`
4. Algum `AJUSTES` (sem rejeitar) → volta para `rascunho`
5. Todos `APROVAR` → publica (`status=publicada`, `publicada_em=now`)

### Tasks ([apps/acervo/tasks.py](apps/acervo/tasks.py)) e Signals ([apps/acervo/signals.py](apps/acervo/signals.py))

- `task_sortear_revisores(analise_id)`: roda `executar_sorteio` +
  envia e-mails (cega oculta autoria; estrutural inclui nome).
- `task_avaliar_apos_revisao(analise_id)`: roda `avaliar_apos_revisao`
  + envia e-mail de boas-vindas (publicação) ou informativo (volta para
  rascunho).
- `task_verificar_prazos()`: cron diário, tenta re-sortear cada
  revisão expirada.
- Signals em `Analise` e `Revisao` capturam estado anterior em
  `_status_anterior` / `_concluido_anterior` no `pre_save` e disparam
  `async_task` no `post_save` apenas em transições específicas.
  Idempotentes.

### Views, templates e mascaramento

- `minhas_revisoes_view`: pendentes (ordenadas por prazo) + 20
  últimas concluídas. Badge violeta "autoria oculta" nas cegas.
- `revisar_view`: form de parecer + comentários ancorados por 8 campos
  (`objeto`, `objetivo`, `foco`, `metodologia`, `resultados`,
  `aspectos_relevantes`, `definicao_extraida`, `resenha_critica`).
  Quando `revisao.tipo=='cega'`, flag `eh_cega=True` ao template
  **suprime totalmente o nome_exibicao e username do analista** —
  testado.
- Templates `minhas_revisoes.html` e `revisar.html` estilizados com
  Tailwind, com aviso destacado em cegas e indicação visual do tipo
  de revisão.

## Critério de aceite (spec §10 — Fase 4)

- [x] Sorteio automático: 2 estruturais + 2 cegos (se há resenha)
- [x] Worker `django-q2` (entra no compose nesta fase)
- [x] Tela "Minhas revisões pendentes"
- [x] **Mascaramento de autoria nas revisões cegas** (verificado em
  testes que `nome_exibicao` e `username` do autor não vazam para a
  página)
- [x] Formulário de revisão com comentários ancorados por campo
- [x] Lógica de transição de status (todas as combinações cobertas)
- [x] Re-sorteio por prazo expirado (`task_verificar_prazos`)
- [x] Exclusão do autor e dos autores de outras análises do mesmo artigo
- [x] Fila de espera quando faltam revisores (`fila_de_espera=True` +
  status mantido em `submetida`)
- [x] **Aceite formal**: análise com resenha passa por 4 revisões com
  autoria oculta nas cegas e é publicada automaticamente — confirmado
  em `test_aprovacao.py::TestFluxoCompletoComResenha` e em shell manual
  end-to-end.

### Cenários CLAUDE.md §9.2 — todos cobertos

| # | Cenário | Teste |
|---|---|---|
| 1 | Sorteio com revisores suficientes | `TestSorteioComRevisoresSuficientes::test_sorteio_normal_cria_2_estruturais` |
| 2 | Sorteio com revisores insuficientes (fallback) | `TestSorteioInsuficiente::test_so_um_revisor_disponivel_vai_para_fila_de_espera` |
| 3 | Re-sorteio por prazo expirado | `TestReSorteioPrazo::test_re_sortear_substitui_o_revisor` |
| 4 | Aprovação por 2 revisores → publicação | `TestAprovacaoSemResenha::test_dois_aprovar_publica` |
| 5 | 1 ajustes + 1 aprovação → volta para rascunho | `TestAprovacaoSemResenha::test_um_ajustes_volta_para_rascunho` |
| 6 | Revisor que é autor da análise é excluído | `TestSorteioRespeitaExclusoes::test_autor_da_analise_nao_eh_sorteado` |
| 7 | Revisor que tem outra análise do mesmo artigo é excluído | `TestSorteioRespeitaExclusoes::test_analista_de_outra_analise_do_mesmo_artigo_eh_excluido` |

## Decisões tomadas

- **Sorteio com `random.shuffle`** em vez de `?random` no SQL: evita o
  preço do `ORDER BY RANDOM()` para listas curtas (poucos analistas).
- **Sem persistir revisões parciais** quando faltam revisores: ou cria
  todas e move para `em_revisao`, ou nenhuma e mantém `submetida` +
  flag `fila_de_espera`. Curador vê no admin.
- **`re_sortear` mantém o `pk` da Revisao** original (só troca
  `revisor` e `prazo_em`) — preserva referências externas (logs, e-mails
  já enviados) e o histórico de quem foi sorteado primeiro pode ser
  reconstruído via auditoria.
- **Cron de prazos é tarefa explícita**, não signal de tempo. Roda
  diário via django-q2 schedule (a configurar no setup do worker em prod).
- **Mascaramento via flag no contexto** + template condicional, em vez
  de subclasse de queryset que reescreve `analista`. Mais simples e
  testável.
- **Comentários ancorados ficam em `ComentarioRevisao`** com `campo`
  string (não FK para um catálogo de campos). Funciona com qualquer
  nome de campo da `Analise` e tolera evolução do modelo.
- **Notificações são best-effort** (`fail_silently=True`): falha de
  e-mail não derruba publicação.
- **Worker no compose com profile `worker`**: dev iterativo não
  precisa do container; em prod o profile é default. Equilibra
  realismo vs. velocidade local.
- **`Q_CLUSTER.sync=True` em dev/test**: mesma codebase roda
  síncrono (sem worker) ou assíncrono (com worker) sem mudar nada nas
  views/signals.

## Desvios da especificação

- **Prazo de revisão estrutural mede 13–14 dias dependendo do segundo**
  (precisão de timezone). Spec diz "+14 dias" exato; o teste tolera
  `13 ≤ delta.days ≤ 14`.
- **Tela "fila de espera" para curador não foi feita** — `fila_de_espera`
  é estado retornado pelo serviço, mas não há UI dedicada (curador
  pode filtrar análises com `status=submetida` e sem revisões no
  admin). Adiável para Fase 6 (dashboard administrativo).
- **`task_verificar_prazos` não é agendada automaticamente** ao subir
  o worker — precisa ser criada via `Schedule.objects.create` no
  bootstrap (ou pelo curador no admin do django_q). Adiável para
  Fase 7 (provisionamento prod).

## Dívida técnica deixada

- **Sem aviso visual de "fila de espera" para o analista** quando
  faltam revisores. Hoje a análise fica em `submetida` em silêncio.
  Email opcional ao curador resolveria.
- **`History` da `Analise` preserva nomes do autor**: se um revisor
  cego abrir a aba de histórico, vê o nome em entries antigas. Spec
  §5.4 fala em "histórico com nomes anonimizados" — implementar custom
  history adapter ou view que filtra a saída para revisores cegos é
  trabalho não trivial; ficou para uma futura iteração quando o
  histórico for exposto na UI da revisão.
- **Notificações de e-mail são síncronas dentro da task**: se SMTP
  estiver lento, a task fica presa. Mover para sub-task aninhada em
  prod.
- **Sem template de e-mail HTML**: tudo em texto puro. Aceitável.
- **Sem rate limiting**: revisor pode submeter parecer 2x se clicar
  rápido (form não tem proteção CSRF dupla nem debounce). Constraint
  `(analise, revisor, tipo)` no banco impede duplicação.

## Métricas

- **Cobertura**: 92% (1.359 statements, 107 misses).
- **Testes**: **192** (34 novos: 19 sorteio + 8 aprovação + 7 views revisão).
- **Linhas adicionadas**: ~1.430 (services + tasks + signals + 2
  templates + 3 arquivos de teste + 1 form/view).
- **Arquivos criados**: 9.
- **Tempo aproximado da fase**: ~1h.

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 5:

1. **Schedule do `task_verificar_prazos`**: configurar antes do deploy.
   Opções: comando `manage.py` que cria o `Schedule`, ou criar via
   admin do django_q. Sugestão: `apps/acervo/management/commands/
   setup_q_schedules.py` na Fase 7 quando provisionarmos prod.
2. **Subir o worker em desenvolvimento real-uso**: `docker compose
   --profile worker up -d` quando quiser testar com tasks reais
   assíncronas.
3. **Promover seu usuário a `curador`** se quiser observar as
   notificações (a task envia e-mail aos revisores via console).

**Aprovação para iniciar a Fase 5** (Acervo público: listagem
facetada, busca FTS, página do artigo `/artigo/<doi-slug>/`, página da
análise `/analise/<id>/`, citação ABNT/APA, selo CC-BY-NC, URLs
estáveis e citáveis) é o próximo passo.
