# Relatório — Separação ANCO × PRISMA · Fase D (ativação global + por usuário)

Branch: `refactor-separacao-anco-prisma`. Em produção.

## O que foi entregue

**Navegação (descoberta dos módulos):**
- `/painel/` ganhou a seção **"Suas revisões"** com **abas** (Alpine):
  *Revisão de escopo · PRISMA-ScR* e *Revisão ANCO · Análise Cognitiva*. Cada aba
  lista os projetos do usuário naquele módulo e leva ao módulo certo
  (`/triagem/` ou `/anco/`). Resolve o "sumiço" do projeto ANCO após a separação.

**Ativação global:** settings `PRISMA_ATIVO` (default True) e `ANCO_ATIVO`
(default False; ON em prod/dev via `.env`). Controlam rotas + visibilidade.

**Acesso por usuário:** `User.pode_prisma` (default True) e `User.pode_anco`
(default False). Métodos `User.acessa_prisma()` / `acessa_anco()` combinam o
global + o por-usuário (admin/staff sempre acessa).

**Guardas:** decorators do `apps/triagem` (`_exige_analista`,
`_projeto_analista`, `_projeto_curador`) checam `acessa_prisma`; os do
`apps/anco` checam `acessa_anco`. O painel só lista cada módulo se o usuário acessa.

**Admin:** `UserAdmin` com ações em massa — *Conceder/Revogar acesso ANCO* e
*PRISMA-ScR* — e os campos `pode_prisma`/`pode_anco` na ficha.

**Migração 0005 (core)** com backfill: quem já é membro de algum projeto ANCO
recebe `pode_anco=True` (não perde acesso). Verificado em prod: **23 usuários**.

## Deploy e verificação
- Ordem (adição de colunas usadas pelo código novo): **migrate → recriar web**.
- Prod: 23 com `pode_anco=True`, 26 com `pode_prisma=True`; sua conta
  `acessa_anco=True`. Healthz 200.

## Testes
Suíte: **550 verde**. Novos testes: aba ANCO no painel; gate de módulo (membro
sem `pode_anco` → 403).

## Próxima fase
**E**: aposentar o redirect transitório (`_anco_movido`), mover `ANCO_ATIVO`/
`PRISMA_ATIVO` para config de admin se desejado, atualizar `CLAUDE.md`/docs,
**merge da branch na `main`**, e **integração do ASReview** (relevância do PRISMA).
