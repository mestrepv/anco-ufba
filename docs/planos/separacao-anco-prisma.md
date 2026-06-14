# Plano — Separação ANCO × PRISMA-ScR em módulos independentes

> Status: **proposta, aguardando aprovação**. Decisão registrada: ANCO e
> PRISMA-ScR têm objetivos antagônicos e **não podem se misturar**. Hoje vivem
> sob `apps/triagem` com um campo `ProtocoloTriagem.modo` e ~25 ramificações
> `if eh_anco`. Vamos separá-los em dois módulos independentes.

## Princípios (decididos)

1. **Dois módulos independentes**, cada um com seus models, views, URLs,
   templates e navegação. **Zero `if eh_anco`.** Quebrar/mudar um não afeta o outro.
2. **Encanamento duplicado** (parsers RIS/BibTeX/CSV + algoritmo de dedup): cada
   módulo tem a sua cópia. Sem biblioteca compartilhada — independência total.
3. **PRISMA herda o `apps/triagem` atual** (a triagem É o PRISMA). O ANCO é
   **extraído** para um novo app.
4. **Acervo é o destino comum e global** (`apps/acervo`: Artigo/Análise) — os dois
   módulos promovem/analisam ali. Isso não é "misturar"; é a estante publicada.
5. **Ativação**: cada módulo pode ser ligado/desligado **globalmente** e o acesso
   é concedido **por usuário**.

## Mapa dos módulos

```
apps/
├── acervo/      GLOBAL, inalterado — Artigo, Analise, Resenha (destino dos dois)
├── triagem/     = MÓDULO PRISMA-ScR (após limpeza: só o rigoroso)
└── anco/        = MÓDULO ANCO (novo)
```

### `apps/triagem` (PRISMA) — fica com
- `ProtocoloTriagem` (remover o campo `modo` e `eh_anco`), `ProjetoMembro`,
  `Busca`, `RegistroTriagem`, `DecisaoTriagem`, `ParDuplicataDescartado`,
  `RodadaCalibracao`, `SnapshotProtocolo`.
- Fluxo: protocolo a priori → busca → dedup → **triagem ≥2 revisores / direta** →
  desempate → checklist/κ → fluxograma PRISMA → promoção ao acervo.
- Remover: `autotriagem.py`, `sorteio_analise.py`, `consenso_view`, e todos os
  galhos `eh_anco` em views/templates.

### `apps/anco` (novo) — leva
- Models próprios: `ProjetoANCO` (≈ ProtocoloTriagem sem rigor), `MembroANCO`,
  `FonteImport` (≈ Busca), `ItemCorpus` (≈ RegistroTriagem, **sem estados de
  triagem** — entra direto no corpus), e os de análise:
  `SorteioAnalise`, `AtribuicaoAnalise`, `ConsensoAnalise` (movidos de triagem).
- Cópia própria dos parsers + dedup.
- Fluxo: importar → **corpus** (tudo entra) → sorteio de análise (cota, aleatório)
  → consenso da dupla → Matriz AnCo (via `apps/acervo`).
- **Sem** triagem, sem screening, sem κ/checklist/fluxograma PRISMA.

## Dados de produção (migração por `modo`)

Projetos existentes são separados pelo `ProtocoloTriagem.modo`:
- `modo=rigoroso` → permanece nas tabelas de `triagem` (sem migração de dados).
- `modo=anco` → **data-migration** copia o projeto + fontes + itens de corpus +
  sorteios/consensos para as tabelas novas de `apps/anco`.
- **Idempotente, com `--dry-run` e backup do banco antes.** O `apps/acervo`
  (curado) **nunca é tocado** — só relido para vínculos.

## Ativação (global + por usuário)

- `ModuloConfig` (singleton ou settings): `prisma_ativo`, `anco_ativo` — desliga
  navegação + rotas do módulo no site inteiro.
- Permissão por usuário: `pode_prisma` / `pode_anco` (campos no User ou grupos),
  concedidos pelo admin (ação em massa no `UserAdmin`, como já existe para papéis).
- A navegação e as rotas de cada módulo só aparecem/respondem se: módulo **ativo**
  globalmente **e** usuário com acesso. Caso contrário → 404/redirect.

## Rollout em fases (produção nunca quebra)

**Fase A — Criar `apps/anco` (aditivo, atrás de flag).**
- Novos models + migrations; cópia dos parsers/dedup; views/urls/templates ANCO.
- Data-migration dos projetos `modo=anco` para o novo app (dry-run + backup).
- Flag `anco_ativo` default OFF; validar em paralelo sem desligar o fluxo atual.
- Aceite: projetos ANCO funcionam 100% no novo módulo; testes verdes.

**Fase B — Cortar o fluxo ANCO para o módulo novo.**
- Roteamento dos projetos ANCO passa a usar `apps/anco`; confirmar paridade.
- Aceite: nenhum acesso ANCO cai no `apps/triagem`.

**Fase C — Limpar o `apps/triagem` (vira PRISMA puro).**
- Remover `autotriagem`, `sorteio_analise`, `consenso`, galhos `eh_anco`, campo
  `modo`. Migration de remoção.
- Aceite: zero referência a ANCO no `triagem`; suíte PRISMA verde.

**Fase D — Ativação global + por usuário.**
- `ModuloConfig` + permissões + navegação condicional + ação no admin.
- Aceite: ligar/desligar cada módulo e conceder acesso por usuário funciona.

**Fase E — Aposentar restos.**
- Remover código/migrations órfãos; atualizar `docs/` e `CLAUDE.md`.

Cada fase termina com **Relatório de Fim de Fase** (CLAUDE.md §7) e **aprovação
humana** antes da próxima. Trabalho em branch `refactor-separacao-anco-prisma`.

## Riscos e mitigações

- **Migração de dados** é o ponto sensível → dry-run obrigatório, backup, e
  conferência de contagens (projetos/itens/sorteios) antes e depois.
- **URLs citáveis**: os caminhos `/triagem/p/<slug>/…` de projetos ANCO mudam de
  prefixo (ex.: `/anco/p/<slug>/`). Avaliar redirects 301 dos antigos.
- **`apps/acervo`** compartilhado: manter como está; só os módulos é que mudam.
- **Duplicação dos parsers/dedup**: aceita por decisão; documentar que correções
  de bug precisam ser aplicadas nos dois lugares.
