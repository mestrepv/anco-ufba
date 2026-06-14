# Relatório — Separação ANCO × PRISMA · Fase A (criar `apps/anco`)

Branch: `refactor-separacao-anco-prisma`. Plano: `docs/planos/separacao-anco-prisma.md`.
**Aditiva**: nada do `apps/triagem` foi alterado; produção segue no fluxo atual
(rotas ANCO só montam com `ANCO_ATIVO`, que está **OFF em produção**).

## O que foi entregue

Módulo `apps/anco` completo e independente do `apps/triagem`:

- **Models** (`models.py`): `ProjetoANCO`, `MembroANCO`, `FonteImport`,
  `ItemCorpus` (corpus sem estados de triagem), `SorteioANCO`, `AtribuicaoANCO`,
  `ConsensoANCO`. `related_name` com sufixo `_anco` (coexiste com o triagem).
  Migration `0001` aplicada (tabelas vazias).
- **Encanamento próprio** (cópia): `parsers.py` (RIS/BibTeX/CSV) e `dedup.py`
  (reusa só `normalizar_doi`/`_gerar_identificador_interno` de `apps/acervo`).
- **Lógica**: `importacao.py` (import → corpus + promoção ao acervo),
  `sorteio.py` (aleatório por cota, idempotente), `estatisticas.py` (× bases).
- **UI** (rotas `/anco/`, gated por `ANCO_ATIVO`): projetos, painel (fluxo 3
  passos), importar, corpus (+remover), sortear (+desfazer), estatísticas, equipe.
- **Migração de dados**: `manage.py migrar_anco` (idempotente, `--dry-run`,
  `--reset`). O acervo curado **nunca** é tocado.
- **Testes** (`apps/anco/tests/`): 19 — import/dedup, sorteio, migração, telas.

## Validação contra dados reais (`--dry-run`, sem gravar)

`piloto-revisao-anco`: 23 membros, 2 fontes, 137 registros →
**137 itens de corpus, todos com `Artigo` vinculado (analisáveis)**, 0 removidos,
0 duplicados ignorados. 0 sorteios/consensos (tabelas vazias).

## Critério de aceite
- [x] `apps/anco` funciona ponta a ponta com a flag ON (telas 200, sorteio, import)
- [x] `migrar_anco --dry-run` bate as contagens do projeto real
- [x] `apps/triagem` **intocado**; produção com `ANCO_ATIVO=OFF`
- [x] Suíte verde (ver Métricas)

## Decisões tomadas
- **Encanamento duplicado** (parsers/dedup) por decisão de projeto — documentado
  no topo dos arquivos (corrigir bug nos dois lugares).
- `ItemCorpus` mais simples que `RegistroTriagem` (sem estados de triagem).
- Migração mapeia: DUPLICADO→ignorado, EXCLUIDO→`removido=True`, demais→corpus.
- `ANCO_ATIVO` ligado em **dev/test**, desligado em **prod** (até Fase B).

## Pendências / decisões para o usuário
1. **URLs dos projetos ANCO** mudam de `/triagem/p/<slug>/` → `/anco/p/<slug>/`
   na Fase B. Confirmar redirects 301 dos caminhos antigos.
2. **UI de consenso (revisão dupla)** não foi portada nesta fase (uso nulo hoje:
   0 sorteios/consensos). Os models existem; a tela pode ser um item à parte.
3. **Preview de import (HTMX)** foi simplificado para validação no submit (sem o
   preview ao vivo do PRISMA). Reincluir se desejado.

## Próxima fase (requer aprovação — mexe em produção)
Fase B: `migrar_anco` real (após backup) + ligar `ANCO_ATIVO` em prod + redirects
301 + navegação apontando ANCO para o módulo novo. Conferência de paridade.

## Métricas
- Commits: A.1/A.2 `48f5714`, A.3 `667d05a`, A.4 `223d761`, A.6/A.7 `a0be7b6`, A.5 `1fa3c3b`.
- Testes `apps/anco`: 19 (verdes). Suíte completa: **603 passed, 1 skipped,
  1 xpassed** (baseline da Fase 0 era 584 → +19 do ANCO, zero regressões).
