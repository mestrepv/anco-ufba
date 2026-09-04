# Documentação da Plataforma AnCo

Mapa da documentação do projeto. O `README.md` na raiz descreve **o que** a
plataforma é e como executá-la; esta pasta registra **como** ela foi
especificada, decidida, construída e operada — o rastro que torna o processo
auditável.

A documentação é versionada junto do código: cada decisão de projeto tem um
plano que a antecede e um relatório que a fecha, ambos datados e ligados aos
commits correspondentes.

---

## Como a documentação está organizada

| Pasta | O que guarda | Quando consultar |
|---|---|---|
| [`metodo/`](metodo/) | O protocolo científico da Análise Cognitiva | Para entender **o que** se analisa e com quais critérios |
| [`especificacao/`](especificacao/) | Especificação técnica do sistema | Para entender **como** o sistema foi projetado |
| [`planos/`](planos/) | Planos escritos **antes** de cada frente de trabalho | Para ver a alternativa escolhida e as descartadas |
| [`relatorios/`](relatorios/) | Relatórios escritos **depois** de cada fase entregue | Para ver o que de fato foi feito, e o que ficou pendente |
| [`migracao/`](migracao/) | Auditoria da base legada que originou o acervo | Para rastrear a procedência dos dados de fundação |
| [`busca_semantica/`](busca_semantica/) | Modelo de embeddings, avaliação e resultados | Para avaliar a qualidade da busca |
| [`operacao/`](operacao/) | Deploy, backup e restauração | Para colocar no ar ou recuperar o serviço |
| [`artigo/`](artigo/) | Relato de experiência sobre o desenvolvimento | Para acompanhar a produção acadêmica derivada |

Os dados que originaram o acervo ficam fora de `docs/`, em
[`dados/legado/`](../dados/legado/) — são dataset, não documentação.

---

## Método científico

O núcleo conceitual do projeto. Define o objeto da Análise Cognitiva e os
critérios que uma análise precisa satisfazer para entrar no acervo.

- [`metodo/protocolo-anco-analise.md`](metodo/protocolo-anco-analise.md) —
  protocolo das quatro abas do editor de análise (Identificação, Conteúdo,
  Estrutura, Resenha crítica). Documento de referência para analistas.
- [`metodo/orientacoes-analise.md`](metodo/orientacoes-analise.md) —
  orientações de alimentação da base dirigidas aos analistas do PPGDC.
- [`metodo/tutorial-base-anco.md`](metodo/tutorial-base-anco.md) —
  tutorial operacional de uso da base.
- [`metodo/facetacao-epistemologia-froes.md`](metodo/facetacao-epistemologia-froes.md) —
  facetação epistemológica segundo Fróes, usada na classificação.
- [`metodo/proposta-evolucao-matriz-froes.md`](metodo/proposta-evolucao-matriz-froes.md) —
  proposta de evolução da matriz (ainda em discussão com a curadoria).

## Especificação técnica

- [`especificacao/ESPECIFICACAO.md`](especificacao/ESPECIFICACAO.md) —
  especificação principal: modelo de dados, papéis, fluxos e regras.
- [`especificacao/frontend.md`](especificacao/frontend.md) —
  especificação da interface e do sistema visual.
- [`especificacao/adendo-busca-semantica.md`](especificacao/adendo-busca-semantica.md) —
  adendo que estende a especificação com a busca semântica.

## Planos (antes)

Escritos antes de executar, registram a alternativa escolhida e por quê.

- [`planos/separacao-anco-prisma.md`](planos/separacao-anco-prisma.md) —
  separação dos módulos Revisão ANCO e Triagem PRISMA-ScR.
- [`planos/integracao-asreview.md`](planos/integracao-asreview.md) —
  relevância por *active learning* via ASReview.
- [`planos/fase-12-projetos.md`](planos/fase-12-projetos.md) — projetos como
  unidade de trabalho.
- [`planos/fase-13-revisao-anco.md`](planos/fase-13-revisao-anco.md) — modo de
  revisão simplificado.
- [`planos/feat-analista-ux-crossref.md`](planos/feat-analista-ux-crossref.md) —
  preenchimento assistido por Crossref.
- [`planos/RETOMAR.md`](planos/RETOMAR.md) — ponto de retomada corrente.

## Relatórios (depois)

Um relatório por fase entregue, em ordem cronológica. Registram o que foi
feito, o que foi verificado e o que ficou em aberto.

- Fases do backend: [`relatorios/fase-0.md`](relatorios/fase-0.md) …
  [`relatorios/fase-14.md`](relatorios/fase-14.md)
- Fases do frontend: [`relatorios/fase-frontend-0.md`](relatorios/fase-frontend-0.md) …
  [`relatorios/fase-frontend-5.md`](relatorios/fase-frontend-5.md)
- Separação ANCO × PRISMA:
  [`relatorios/separacao-anco-prisma-fase-0.md`](relatorios/separacao-anco-prisma-fase-0.md) …
  [`relatorios/separacao-anco-prisma-fase-d.md`](relatorios/separacao-anco-prisma-fase-d.md)
- [`relatorios/auditoria-tecnica-2026-06.md`](relatorios/auditoria-tecnica-2026-06.md) —
  auditoria técnica independente do código e da arquitetura.
- [`relatorios/feat-analista-ux-crossref.md`](relatorios/feat-analista-ux-crossref.md)

## Procedência dos dados

A base de fundação veio de uma planilha coletiva mantida entre 2018 e 2026.
Estes documentos auditam essa origem — o que foi aproveitado, o que foi
corrigido e o que foi descartado.

- [`migracao/analise_legado.md`](migracao/analise_legado.md)
- [`migracao/auditoria_qualidade.md`](migracao/auditoria_qualidade.md)
- [`migracao/problemas_base_revisada.md`](migracao/problemas_base_revisada.md)

Dataset correspondente em [`dados/legado/`](../dados/legado/):
`base-referencial-original.json` (como recebido) e
`base-referencial-corrigida.json` (após a auditoria de DOIs). Endereços de
e-mail presentes na planilha original foram removidos antes da publicação.

## Busca semântica

- [`busca_semantica/apresentacao-busca-semantica.md`](busca_semantica/apresentacao-busca-semantica.md)
- [`busca_semantica/avaliacao.md`](busca_semantica/avaliacao.md)

## Operação

- [`operacao/DEPLOY.md`](operacao/DEPLOY.md) — deploy em produção.
- [`operacao/RESTORE.md`](operacao/RESTORE.md) — backup e restauração.

## Produção acadêmica

Relato de experiência sobre desenvolver a plataforma em parceria com um agente
de IA. Em elaboração.

- [`artigo/inventario-de-decisoes.md`](artigo/inventario-de-decisoes.md) —
  levantamento retroativo das decisões de projeto, com data, alternativa
  descartada e evidência.
- [`artigo/plano-de-escrita.md`](artigo/plano-de-escrita.md) — plano do artigo.
- [`artigo/relato-experiencia.md`](artigo/relato-experiencia.md) — rascunho.

## Direção

- [`ROADMAP.md`](ROADMAP.md) — fases concluídas e próximos passos.
