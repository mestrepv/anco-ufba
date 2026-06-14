# Relatório — Separação ANCO × PRISMA · Fase 0 (Preparação e inventário)

Branch: `refactor-separacao-anco-prisma`. Plano: `docs/planos/separacao-anco-prisma.md`.

## O que foi entregue
- Branch `refactor-separacao-anco-prisma` criada a partir de `main` (`c49b48b`).
- Inventário de produção por modo.
- Backup completo do banco antes de qualquer mudança.
- Baseline da suíte de testes registrada.

## Inventário (produção, 2026-06-14)

**Projetos por modo:** anco → 1 · rigoroso → 2.

**ANCO (migra para `apps/anco`):**
| slug | membros | buscas | registros | incluídos | decisões | sorteios | consensos |
|---|---|---|---|---|---|---|---|
| `piloto-revisao-anco` | 23 | 2 | 137 | 67 | 0 | 0 | 0 |

Tabelas `SorteioAnalise`/`AtribuicaoAnalise`/`ConsensoAnalise` estão **vazias**
globalmente (0). A migração ANCO é, portanto, pequena: 1 projeto, 2 fontes, 137
itens de corpus, sem sorteios/consensos.

**Rigoroso (permanece em `apps/triagem`):**
| slug | registros |
|---|---|
| `jogos-epistemicos-e-dbr` | 553 |
| `analise-cognitiva-teste` | 0 |

## Backup
- `backups/pre-separacao-anco-prisma_20260614_121629.sql` (28 MB; fora do git).

## Baseline de testes
- `pytest` completo: **584 passed, 1 skipped, 1 xpassed** (~208 s).

## Critério de aceite
- [x] Inventário levantado
- [x] Backup do banco feito
- [x] Baseline verde registrada

## Próxima fase
Fase A — criar `apps/anco` (aditivo, atrás de flag) + comando `migrar_anco`.
Não toca `apps/triagem` nem o acervo. Termina com relatório + aprovação.
