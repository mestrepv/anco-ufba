# Relatório — Fase 13: Revisão ANCO (modo simplificado de triagem + sorteio de análise)

> Plano: [`docs/planos/fase-13-revisao-anco.md`](../planos/fase-13-revisao-anco.md).
> Parecer de origem: `PARECER_triagem_simplificada_matriz_ANCO.md`.
> Branch: `fase-13-revisao-anco`. Migration: `triagem 0020`.

## O que foi entregue

Um **modo de operação por projeto** (`ProtocoloTriagem.modo ∈ {rigoroso, anco}`,
default `rigoroso`) que liga a **Revisão ANCO** ao lado do PRISMA-ScR, **sem
remover nada** do protocolo rigoroso (Fases 9–12).

- **Modelo** (`apps/triagem/models.py`): campo `modo` + `eh_anco`;
  `RegistroTriagem.relevancia_score`; modelos novos `SorteioAnalise`,
  `AtribuicaoAnalise`, `ConsensoAnalise`. Migration aditiva `0020` (acervo curado
  intocado).
- **Autotriagem** (`autotriagem.py`): o dono da base tria a própria base (revisor
  único), reusando a consolidação de `aprovacao` e a promoção ao acervo. Gate de
  propriedade espelha a dedup (`importadores`); só no modo ANCO.
- **Relevância** (`relevancia.py` + comando `recalcular_relevancia`): nº de termos
  da estratégia de busca presentes no título/resumo/palavras-chave (sem
  embeddings). Cacheado em `relevancia_score`, recalculável.
- **Sorteio da análise** (`sorteio_analise.py`): cota (5) por analista,
  diversidade de base como **preferência** (nunca bloqueia), prioriza relevância,
  `unica`/`dupla`. Idempotente; registra faltas quando o pool é insuficiente.
- **Consenso** (revisão dupla): o curador registra a análise final; as duas de
  origem ficam como insumo.
- **Views/URLs/templates**: `autotriar`, `incluidos`, `sorteio-analise`,
  `consenso`; `a-analisar` passa a mostrar **só os artigos atribuídos** quando há
  sorteio; painel ciente do modo (rótulo "Revisão ANCO", ações ANCO, oculta
  PRISMA/κ/checklist/calibração no modo ANCO).
- **Admin**: `modo` no `ProtocoloTriagem`; admin de `SorteioAnalise`
  (+inline de atribuições), `AtribuicaoAnalise`, `ConsensoAnalise`.

## Critério de aceite (do plano §7)
- [x] Projeto ANCO: importar → deduplicar (próprias+cruzadas) → autotriar → ver
  incluídos por relevância → sortear 5/analista de bases diferentes → analista vê
  só os seus → (dupla) curador concilia.
- [x] Projeto rigoroso idêntico às Fases 9–12 (sem regressão — suíte verde).
- [x] Acervo curado intocado; migração aditiva.
- [x] Rótulos PRISMA/κ ausentes na UI do modo ANCO; presentes no rigoroso.
- [x] Cobertura ≥70% nas linhas novas (**98%** nos módulos de domínio).

## Decisões tomadas (confirmadas pela coordenação)
- Relevância **pondera o sorteio** (não só a lista).
- Diversidade de base é **preferência, não regra dura**.
- O **curador** decide única/dupla no sorteio e **concilia** a dupla.
- Consenso via `ConsensoAnalise`; embeddings **fora** (relevância por termos).
- Autotriagem aceita **incluir/excluir** (sem `dúvida`, para não criar desempate).

## Desvios da especificação
Nenhum em relação ao plano. O plano em si é um desvio **deliberado e aditivo** do
fluxo PRISMA-ScR, comutado por `modo` e reversível por projeto.

## Dívida técnica deixada
- **Consenso é mínimo**: registra qual análise é a final; não há tela de
  comparação lado a lado nem geração assistida da análise consolidada.
- **Independência na dupla**: o algoritmo não evita atribuir um artigo ao
  importador da sua base (nice-to-have; diversidade já é preferida).
- Relevância semântica (embeddings/base referencial) fica como evolução futura.

## Métricas
- Cobertura dos módulos novos: **98%** (relevancia 98%, autotriagem 97%,
  sorteio_analise 99%).
- Testes: **392 passed, 1 skipped** (triagem+acervo); **24** novos (Fase 13).
- Migration: `triagem 0020` (3 modelos + 2 campos). Lint `ruff` limpo.

## Pendências para o usuário
- Criar um **projeto em modo ANCO** (admin → ProtocoloTriagem → `modo = anco`) e
  designar membros analistas/curador para a validação parcial.
- Após a triagem, rodar `manage.py recalcular_relevancia --projeto <slug>` (ou
  confiar no cálculo na inclusão) antes do primeiro sorteio.
- Avaliar se a tela de **consenso** precisa de comparação lado a lado já nesta
  rodada de validação ou se o registro mínimo basta.
</content>
