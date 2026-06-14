# Retomar amanhã — onde paramos (2026-06-14)

## ✅ Concluído e em produção (na `main`)
A **separação ANCO × PRISMA** está completa (Fases 0→E):
- `apps/anco` = módulo **Revisão ANCO** independente (import → corpus → sorteio → análise), em `/anco/`.
- `apps/triagem` = **PRISMA-ScR puro** (sem `modo`, sem relevância interna, sem sorteio de análise).
- `/painel/` com **abas PRISMA × ANCO**; acesso por usuário (`pode_prisma`/`pode_anco`).
- **Revisor independente** por membro: o curador define quantos revisores; "Iniciar triagem" usa só eles.
- **Terreno do ASReview** preparado (relevância do PRISMA virá dele).

Relatórios: `docs/relatorios/separacao-anco-prisma-fase-0..d.md`.
Planos: `docs/planos/separacao-anco-prisma.md` e `docs/planos/integracao-asreview.md`.

## ▶️ Próximos passos (retomar por aqui)

### 1. Piloto do ASReview (abordagem A — serviço ao lado)
```bash
# exportar o corpus de um projeto PRISMA em CSV (formato ASReview)
docker compose -f infra/docker-compose.yml exec web \
  python manage.py exportar_corpus jogos-epistemicos-e-dbr --saida /tmp/corpus.csv
docker compose -f infra/docker-compose.yml cp web:/tmp/corpus.csv ./corpus.csv

# subir o ASReview LAB (opt-in, só localhost por segurança)
docker compose -f infra/docker-compose.yml --profile asreview up -d asreview
# acessar via túnel:  ssh -L 9091:127.0.0.1:9091 <servidor>  →  http://localhost:9091
#   (porta host 9091: milhar 9000 deste projeto — web=9090, asreview=9091)
```
Triar um trecho com active learning; anotar a **regra de parada (SAFE)** e o **recall**.
> Alternativa mais simples para o 1º teste: rodar o ASReview **localmente**
> (`pip install asreview`, precisa Python 3.10+; temos 3.12) e subir o `corpus.csv`.

### 2. Decisão metodológica (curadoria / professoras)
**1 revisor assistido por AL vs 2 revisores independentes?** Define o desenho e a
publicabilidade (ASReview aceita os dois; relatar modelo + regra de parada + recall).

### 3. Importar de volta (depois da decisão)
Criar `manage.py importar_triagem_asreview` + campo `RegistroTriagem.prioridade_asreview`.
Ponto de extensão já existe: `apps/triagem/asreview.py`.

### 4. Limpezas futuras (opcionais)
- Aposentar o redirect transitório `_anco_movido` (em `apps/triagem/views.py`) quando
  não houver mais links antigos `/triagem/p/<anco-slug>/`.
- Mover `ANCO_ATIVO`/`PRISMA_ATIVO` do `.env` para uma config editável no admin.

## 🔧 Operacional
- Produção serve a `main` (bind-mount). Deploy de template/Python:
  `docker compose -f infra/docker-compose.yml up -d --force-recreate web`.
- `ANCO_ATIVO=True` vive no `.env` do servidor (fora do git).
- Backups do banco em `/home/anco-paulovicente/backups/`.
- Branch do refactor: `refactor-separacao-anco-prisma` (já mesclada na `main`).
