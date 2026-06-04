# Relatório — Fase 10: Operacionalizar a triagem no fluxo

Amarra a triagem (Fase 9) ao uso real: **cada analista sobe uma base por período**,
o sistema **aponta as duplicatas** antes de triar, o **curador inicia** a triagem ao
fechar a coleta, e **só os triados (incluídos) entram na análise**.

Decisões (confirmadas): revisão **única cumulativa**; **curador** inicia a triagem;
**só triados** na análise (avulso → curador/admin); dedup **automática + possíveis
duplicatas** por similaridade.

## Sub-fases

| Sub-fase | Entrega | Status |
|---|---|---|
| **10.1** | Tela de **resumo da importação** (`/triagem/busca/<id>/`): novos · duplicados entre bases · já no acervo · ignorados, persistidos na `Busca`. | ✅ |
| **10.2** | **Possíveis duplicatas** por similaridade de título (`pg_trgm`/`TrigramSimilarity`) — casos sem DOI ou com DOI divergente; `/triagem/duplicatas/` com **mesclar** (DUPLICADO + `duplicado_de` + funde origens) ou **descartar** (`ParDuplicataDescartado`). DUPLICADO não é sorteado. | ✅ |
| **10.3** | **Iniciar triagem é ação do curador** (gate de coleta) com tela de confirmação; botão só para curador/admin. | ✅ |
| **10.4** | **Só triados na análise**: ponte `/triagem/a-analisar/` (incluídos sem análise do usuário → botão **Analisar** via `iniciar_analise`) + **trava** no cadastro avulso (`cadastrar_artigo_view`: criar Artigo novo exige curador/admin; analista é redirecionado a "a analisar"). Nav ajustado. | ✅ |

## Fluxo operacional resultante

1. Analista **importa** a base (RIS/BibTeX/CSV) → vê o **resumo da dedup**.
2. Revisa **possíveis duplicatas** (mescla/descarta).
3. **Curador fecha a coleta** e **inicia a triagem** (sorteia ≥2 revisores).
4. Revisores triam (mascarado) → consenso/desempate → **incluídos viram `Artigo`**.
5. Analistas pegam os incluídos em **"A analisar"** → preenchem a Matriz AnCo.
6. Curadoria publica. **Fluxograma PRISMA** acompanha tudo.

## Decisões de implementação
- "Triado" para liberar análise = `Artigo` **incluído na triagem** OU **já no acervo**
  (legado/existente). Criar Artigo **novo** é exclusivo de curador/admin.
- Dedup determinística (DOI/ISBN/hash) continua automática; a similaridade de título
  (`pg_trgm`, limiar 0.6) só **sugere** pares para um humano confirmar.
- "Fechar a coleta" não é estado persistente (revisão cumulativa): é o **ato do curador**
  de iniciar a triagem quando julga o período completo.

## Métricas / verificação
- Migrations: `0003` (contagens da Busca), `0004` (`pg_trgm`), `0005` (`ParDuplicataDescartado`).
- Testes: +20 (resumo, duplicatas, gate do curador, bloqueio do avulso, ponte). Aditivo;
  nenhuma mudança no modelo `Analise`.
- Deploy: migrations + `restart web` (rotas novas + `pg_trgm`).

## Pendências para o usuário
- Definir os **critérios reais** no admin (Protocolos de triagem) e habilitar **revisores**.
- (Opcional, futuro) cálculo de **kappa** de concordância entre revisores.
