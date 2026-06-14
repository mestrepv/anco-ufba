# Relatório — Separação ANCO × PRISMA · Fase B (rotear ANCO para o módulo novo)

Branch: `refactor-separacao-anco-prisma`. **Primeira fase que tocou produção.**

## O que foi feito (produção)
1. **Backup** pré-migração: `backups/pre-faseB-migracao-anco_20260614_130350.sql` (28 MB).
2. **Migração real** (`manage.py migrar_anco`) do projeto `piloto-revisao-anco`:
   - 23 membros, 2 fontes, **137 itens de corpus** (todos com `Artigo` e ≥1 fonte).
   - 0 sorteios/consensos (tabelas vazias). Acervo curado **intocado**.
3. **Flag ligada**: `ANCO_ATIVO=True` no `.env` de produção (fora do git).
4. **Redirect 301**: rotas `/triagem/p/<slug>/…` de projeto `eh_anco` →
   `/anco/p/<slug>/…` (nos decorators de projeto do triagem). Projetos rigorosos
   seguem no triagem.
5. **Deploy**: `--force-recreate web`. Healthz 200; rotas `/anco/` e `/triagem/`
   respondem (302→login, sem 404/500).

## Verificação
- Contagens migradas conferidas no banco de produção (23/2/137).
- Rotas no ar: `/anco/`, `/anco/p/piloto-revisao-anco/`, redirects e triagem
  rigoroso — todas 302 (login) para anônimo; nenhuma 404/500.
- Suíte: 603 passed (Fase A) + redirects testados (`test_redirect.py`).

## Estado do deploy
- **Produção serve a branch** `refactor-separacao-anco-prisma` (bind-mount da
  árvore de trabalho). `main` permanece em `c49b48b` para revisão/merge.
- Reversível: `ANCO_ATIVO=False` no `.env` + recriar `web` → volta ao triagem
  (os dados migrados ficam, inofensivos).

## Pendência operacional (não versionada)
- `ANCO_ATIVO=True` vive no `.env` do servidor. Registrar no provisionamento.

## Próxima fase (DESTRUTIVA — requer aprovação)
Fase C: limpar `apps/triagem` (remover models/arquivos/branches ANCO + campo
`modo`). É irreversível sem revert. **Antes**, validar a paridade logando como
membro do `piloto-revisao-anco` e conferindo o fluxo no `/anco/`.
