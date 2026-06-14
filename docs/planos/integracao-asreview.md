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

## Piloto — pronto para rodar (Abordagem A)

Terreno já preparado:

1. **Exportar o corpus** de um projeto PRISMA em CSV (colunas do ASReview):
   ```
   docker compose -f infra/docker-compose.yml exec web \
     python manage.py exportar_corpus jogos-epistemicos-e-dbr --saida /tmp/corpus.csv
   docker compose -f infra/docker-compose.yml cp web:/tmp/corpus.csv ./corpus.csv
   ```
   Colunas: `record_id,title,abstract,authors,year,doi,keywords,journal,label_included`
   (label 1/0 = decisões já tomadas; vazio = a triar). Duplicatas omitidas.

2. **Subir o ASReview LAB** (opt-in, só localhost por segurança):
   ```
   docker compose -f infra/docker-compose.yml --profile asreview up -d asreview
   ```
   Acessar via **túnel SSH** (`ssh -L 9091:127.0.0.1:9091 servidor`) → http://localhost:9091.
   (porta host **9091**: milhar 9000 deste projeto — web=9090, asreview=9091; a 5000 já é
   usada pelo dev server Vite de outro projeto neste servidor.)
   > **Não** publicar pelo Caddy sem auth — o ASReview LAB v1 não tem login.
   > Para acesso multiusuário/remoto, avaliar o ASReview LAB v2 (com autenticação).

3. **Triar no ASReview**: criar projeto, subir o `corpus.csv`, marcar alguns
   prior-knowledge (relevantes/irrelevantes), e screenar com active learning.

4. **Avaliar**: registrar a regra de parada usada e o recall; levar à curadoria a
   decisão de 1 vs 2 revisores (ver §"O catch" acima).

Importar os rótulos/ordem de volta para os `RegistroTriagem` é o passo seguinte
(após a curadoria decidir o desenho) — exigirá um comando `importar_triagem_asreview`
+ o campo `prioridade_asreview`.

## Checklist da integração (futuro)
- [ ] Escolher abordagem (A ou B) com o usuário.
- [ ] (A) Adicionar serviço `asreview` ao `infra/docker-compose.yml` + Caddy/auth.
- [ ] (A) Export do corpus (RIS/CSV) e import do ranking/rótulos.
- [ ] (B) Verificar Python API/`asreview simulate`; rodar AL sobre o corpus.
- [ ] Campo `prioridade_asreview` + ordenação da fila por ele.
- [ ] Testes + docs.
