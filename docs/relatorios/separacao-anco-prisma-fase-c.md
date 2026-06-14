# Relatório — Separação ANCO × PRISMA · Fase C (limpar o triagem → PRISMA puro)

Branch: `refactor-separacao-anco-prisma`. Conclui a separação: `apps/triagem`
fica **PRISMA-ScR puro**; ANCO vive em `apps/anco`.

## Decisão adicional
**Relevância sai do PRISMA** — será fornecida pelo plugin externo **ASReview**
(active learning), integrado depois. O `relevancia_score`/`relevancia.py` (termo-
matching, originalmente ANCO) é removido. Viável: no PRISMA o score era gravado
mas nunca lido (só o sorteio do ANCO lia).

## Entregas

**C.1 — redirect desacoplado do `modo`** (`807b…` antes): os caminhos
`/triagem/p/<slug>/` de projeto migrado redirecionam (301) a `/anco/` por
existência do slug em `ProjetoANCO` (não dependem mais de `eh_anco`).

**C (código)** — commit `742ba96`: remove do `apps/triagem` views/rotas
(`autotriar`, `sorteio_analise`, `consenso`, `incluir_corpus`, `estatisticas`,
`excluir_incluido`), arquivos (`autotriagem`, `sorteio_analise`, `relevancia`,
`estatisticas`) + comandos, hooks ANCO de `aprovacao`/`importacao`, e o código
ANCO do `apps/core` (painel). Templates ANCO deletados. Testes ANCO removidos.

**C (destrutiva)** — commit `807b52b` + migration **0022**:
- `RemoveField` `modo` (ProtocoloTriagem), `relevancia_score` (RegistroTriagem
  + histórico). `DeleteModel` SorteioAnalise, AtribuicaoAnalise, ConsensoAnalise.
- `RunPython` arquiva os projetos que eram `modo=anco` antes do drop.
- Views `a_analisar`/`incluidos` viram **pool self-serve** (sem sorteio);
  `novo_projeto` sem seletor de modo; `templatetag a_analisar_count` e core
  painel simplificados; ramos `{% if eh_anco %}` removidos dos templates;
  "Artigo individual → corpus" (ANCO) desativado no acervo; `migrar_anco` removido.

## Deploy (produção) e verificação
1. **Backup**: `backups/pre-faseC-destrutiva_20260614_135946.sql` (28 MB).
2. **Ordem segura**: deploy do código novo (não referencia `modo`/`eh_anco`) →
   depois `migrate triagem` (drop das colunas/tabelas). Janela sem incompatibilidade.
3. **Verificado em prod**: coluna `modo` removida; `relevancia_score` removido;
   tabelas sorteio/atribuição/consenso dropadas; `piloto-revisao-anco` arquivado
   (fora da lista PRISMA, redireciona a `/anco/`); healthz 200; rotas 302 (sem 500).

## Testes
Suíte: **549 verde** (1 skip, 1 xpass). Testes ANCO migraram para `apps/anco`
(19 testes). `apps/acervo` intocado no comportamento.

## Estado final
- `apps/triagem` = **PRISMA-ScR puro** (sem `modo`, sem ANCO, sem relevância).
- `apps/anco` = **Revisão ANCO** independente, em produção.
- Redirect transitório dos slugs migrados (`_anco_movido`) permanece como ponte.

## Próximas fases (do plano)
- **D**: ativação global + por usuário (`ModuloConfig` + `pode_prisma`/`pode_anco`).
- **E**: aposentar restos (redirect transitório, `ANCO_ATIVO` → config), docs,
  e **integração do ASReview** para relevância.
