# Plano — Integração do ASReview (relevância do PRISMA-ScR)

> Status: **terreno preparado, integração pendente**. Contexto: na separação
> ANCO × PRISMA (Fase C) removemos a relevância interna (`relevancia_score`,
> termo-matching). A relevância do módulo PRISMA passará a vir do **ASReview**.

## O que o ASReview faz
**ASReview LAB** é uma ferramenta open-source de *active learning* para triagem
de revisões sistemáticas: o humano rotula alguns registros (incluir/excluir) e o
modelo **reordena a fila**, mostrando primeiro os mais prováveis de serem
relevantes. No nosso PRISMA-ScR (triagem por ≥2 revisores), o papel do ASReview
é **priorizar a ordem da fila de triagem** — não substituir a decisão humana.

## Instalação (referência)
- Requer **Python 3.10+**.
- `pip install asreview` → `asreview lab` (web, porta 5000 por padrão).
- Docker: `ghcr.io/asreview/asreview:latest lab`.
- Aceita **RIS / CSV / TSV / Excel** como entrada; exporta os rótulos/ordem.
- Docs: https://asreview.readthedocs.io/en/stable/lab/installation.html

## Duas abordagens de integração

### A) Serviço ao lado (acoplamento frouxo) — recomendado para começar
ASReview LAB roda como um **serviço próprio** no Docker Compose, atrás do Caddy
(com auth). Fluxo:
1. O curador **exporta** o corpus do projeto (RIS/CSV) da nossa triagem.
2. Sobe no ASReview LAB e tria/prioriza lá (active learning).
3. **Importa de volta** a ordem/rótulos para os `RegistroTriagem`.

- **Prós:** zero acoplamento de código; usa o app oficial, mantido upstream.
- **Contras:** passo manual de export/import; duas telas.
- **Esforço:** baixo (um serviço no Compose + um import/export).

### B) Programática (acoplamento forte)
Usar o **Python API / CLI** do ASReview dentro de um serviço Django: rodar o
*active learning* sobre o corpus e **gravar a ordem de relevância** nos
`RegistroTriagem`, usada para ordenar a fila de triagem na nossa própria UI.

- **Prós:** uma experiência só (a fila já vem priorizada na nossa tela).
- **Contras:** acopla a uma versão do `asreview`; precisa rodar AL (CPU/tempo)
  e modelar o estado do aprendizado; a API/feature-extraction precisa ser
  verificada na implementação.
- **Esforço:** médio/alto.

**Recomendação:** começar pela **(A)** (valor rápido, baixo risco) e evoluir
para **(B)** se o fluxo manual incomodar.

## Ponto de extensão já no código
`apps/triagem/asreview.py` (scaffolding): define a interface onde a relevância
do ASReview vai entrar — `prioridade_para(projeto)` (ranking por registro) e
`aplicar_ranking(projeto, ranking)`. Hoje levantam `NotImplementedError` com a
nota da abordagem a escolher. Quando integrarmos:
- Se **(A)**: `aplicar_ranking` recebe o export do ASReview e grava nos registros.
- Se **(B)**: `prioridade_para` roda o AL e devolve o ranking.

## Dados
Para ordenar a fila por relevância, reintroduzir um campo leve em
`RegistroTriagem` (ex.: `prioridade_asreview = PositiveIntegerField(null=True)`)
**no momento da integração** — não agora (evita campo morto). A ordenação da
triagem (`/registros/`, sorteio/atribuição) passaria a usá-lo quando presente.

## Checklist da integração (futuro)
- [ ] Escolher abordagem (A ou B) com o usuário.
- [ ] (A) Adicionar serviço `asreview` ao `infra/docker-compose.yml` + Caddy/auth.
- [ ] (A) Export do corpus (RIS/CSV) e import do ranking/rótulos.
- [ ] (B) Verificar Python API/`asreview simulate`; rodar AL sobre o corpus.
- [ ] Campo `prioridade_asreview` + ordenação da fila por ele.
- [ ] Testes + docs.
