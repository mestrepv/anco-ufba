# Relatório — Fase 14: Revisão ANCO sem triagem prévia

## O que foi entregue

Simplificação do modo `anco` da triagem, por decisão da professora: **acaba a
triagem prévia**. Novo fluxo de cadastramento:

```
Busca → Importação + dedup (inclui TODOS) → Estatística artigos×bases → Sorteio aleatório (5/analista) → Matriz AnCo
```

- **Inclusão automática na importação** — `aprovacao.incluir_automaticamente`
  (status `INCLUIDO` + `promover_para_acervo`, **sem** `DecisaoTriagem`);
  hook no fim de `importacao.importar_para_busca` quando `protocolo.eh_anco`.
  Cobre as duas portas de import (web + `manage.py importar_triagem`). Todos os
  tipos de documento entram (artigo, tese, etc.).
- **Migração para o corpus** — `aprovacao.incluir_corpus_total` inclui os
  `IDENTIFICADO` pendentes **e reinclui os `EXCLUIDO`** da autotriagem antiga
  (via `desfazer_autotriagem`; exclusões antigas viram obsoletas). Exposto como
  `manage.py incluir_corpus --projeto <slug> [--dry-run]` e botão de curador
  (`incluir_corpus_view`).
- **Sorteio aleatório reprodutível** — `executar_sorteio_analise(...,
  aleatorio=True)` embaralha o pool com `random.Random(semente)` (sem relevância
  nem diversidade de base); `SorteioAnalise.semente` registra a seed. Cota=5,
  única/dupla, idempotência preservadas. `sorteio_analise_view` usa
  `aleatorio=projeto.eh_anco`.
- **Estatística artigos × bases** — `estatisticas.estatisticas_por_base` (fonte
  `RegistroTriagem.origem_buscas`, corpus pós-dedup) em
  `/triagem/p/<slug>/estatisticas/` + template.
- **Autotriagem descontinuada** — `autotriar_view` redireciona ao corpus; painel
  ANCO esconde "A triar"/"Triar minha base" e mostra corpus + estatística +
  sorteio; código morto da tela item-a-item removido.
- **Migration** `triagem/0021` (`SorteioAnalise.semente`).

## Critério de aceite

- [x] Importar num projeto ANCO inclui tudo e promove a `Artigo`.
- [x] Duplicadas removidas (dedup da importação, inalterada).
- [x] Estatística consolidada artigos × bases.
- [x] Sorteio aleatório distribui 5 artigos por analista.
- [x] Modo `rigoroso` (PRISMA-ScR) intacto.
- [x] Acervo legado nunca tocado (`ja_no_acervo` permanece `IDENTIFICADO`).

## Decisões tomadas

- **Redefinir o modo `anco`** (não criar 3º modo) — a triagem some da interface;
  o rigoroso é o caminho com triagem.
- **Reincluir exclusões antigas** no corpus (decisão do usuário): a migração
  desfaz `EXCLUIDO` da autotriagem e inclui.
- Sorteio aleatório com **seed gravada** para auditoria/reprodutibilidade
  (Python `random`, não nondeterminismo opaco).
- Inclusão automática **sem revisor fake**: não cria `DecisaoTriagem`;
  `decidida_por=None` (auditável como inclusão automática).

## Desvios da especificação

A especificação original previa triagem por pares; o addendum da Fase 13 já a
simplificara (autotriagem). A Fase 14 remove a triagem do modo ANCO por decisão
de produto registrada — o rigoroso permanece como na especificação.

## Dívida técnica deixada

- Após a auto-inclusão, a `Busca` conta como "triagem iniciada", então o
  importador não exclui mais a própria importação (só o curador, com cascata).
  Aceitável (import = commit ao corpus); revisitar se virar atrito.
- Templates `autotriar.html` e helpers de autotriagem (`autotriar`,
  `registros_para_autotriar`) ficam sem uso no fluxo ANCO; mantidos pois o
  domínio ainda referencia `reverter_inclusao`/`desfazer_autotriagem`.

## Métricas

- Testes: `apps/triagem/tests/` + `apps/acervo/tests/` → **414 passed, 1 skipped**.
- Novos testes: inclusão automática (4), incluir_corpus (3), estatística (2),
  sorteio aleatório (3); 4 testes de autotriagem antigos substituídos.
- Migration: `0021_sorteioanalise_semente`.

## Pendências para o usuário

- Rodar `manage.py incluir_corpus --projeto <slug> --dry-run` em produção para
  conferir quantos registros entram no corpus antes de aplicar.
- Validar o painel/estatística pelo HTTP real (Caddy→gunicorn) com
  `docker compose -f infra/docker-compose.yml up -d --force-recreate web`.
- Revisão das professoras (Fróes/Leliana) ao texto do protocolo atualizado
  (`docs/protocolo-anco-analise.md`).
