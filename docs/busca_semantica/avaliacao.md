# Avaliação Qualitativa — Busca Semântica AnCo

> **Status**: rascunho a preencher (atualizado em 2026-06).
>
> Preencher após `manage.py reindexar_embeddings` popular o acervo de fundação
> (base curada, **653 registros** `legado`) + as análises publicadas. As queries
> dos blocos A–B cobrem casos onde a busca semântica tende a **ganhar** da textual;
> o **bloco C (fronteira)** existe para **medir o viés de canonicidade** — ver §0.
>
> **Modelo**: `paraphrase-multilingual-MiniLM-L12-v2` · 384 dimensões · ~420 MB RAM.

---

## 0. Por que esta avaliação existe (leia antes de preencher)

Dois objetivos, não um:

1. **Qualidade geral** — a busca semântica ajuda mais do que atrapalha? Onde ela
   ganha da textual, onde perde?
2. **Viés de canonicidade (específico da AnCo)** — o modelo foi treinado em texto
   geral, não na obra de Teresinha Fróes. Há o risco de ele representar bem o
   *cânone* e **sub-ranquear justamente as obras de fronteira** — emergentes, de
   terminologia incomum — que o protocolo da AnCo quer **reconhecer** (cf.
   `docs/protocolo-anco-analise.md` §7). O **bloco C** testa exatamente isso.

> Esta avaliação é o **gate de decisão** para a pergunta "vale a pena ajustar
> (fine-tuning) o modelo à AnCo?". Sem medir antes, qualquer ajuste é fé, não
> engenharia — e um ajuste sobre o acervo atual pode **reforçar** o viés do
> bloco C em vez de corrigi-lo. Primeiro medir, depois decidir.

### Como julgar cada query (método)

- Rode os dois modos e registre os **top-5** de cada um.
- Marque a pertinência de cada resultado: **✓** pertinente · **~** parcial · **✗** não.
- Calcule **P@5** (precisão nos 5) por modo = nº de ✓ ÷ 5.
- Para o bloco C, registre também o **indicador de fronteira**: *a obra-alvo de
  fronteira apareceu nos top-5 do semântico?* (Sim/Não). É o número que importa.
- Lance os totais no **placar** da §Conclusões.

---

## Blocos A–B — Qualidade geral (semântico tende a ganhar)

Para cada query: anotar os top-5 resultados de cada modo, a pertinência
subjetiva (✓ pertinente / ~ parcial / ✗ não pertinente) e o score de similaridade.

---

### Query 1 — Termo técnico sinônimo

**Query**: `"análise do discurso científico"`

**Hipótese**: a busca semântica deve retornar análises com termos como
"linguagem científica", "comunicação académica", "retórica da ciência"
que a busca textual perde por divergência de vocabulário.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 2 — Tradução entre línguas

**Query**: `"cognitive analysis of scientific literature"`

**Hipótese**: como o modelo é multilíngue, deve retornar análises sobre
cognição e literatura científica mesmo que estejam escritas em português.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 3 — Conceito abstrato sem termos exatos

**Query**: `"como pesquisadores constroem conhecimento coletivo"`

**Hipótese**: texto conversacional sobre cognição social; busca textual
vai encontrar pouco. Busca semântica deve retornar análises sobre
cognição distribuída, cocriação científica, etc.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 4 — Metodologia específica

**Query**: `"revisão sistemática de literatura"`

**Hipótese**: ambos os modos devem ter boa performance; avaliar se
semântico pega variantes como "mapeamento bibliométrico", "scoping review".

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 5 — Área temática ampla

**Query**: `"educação e cognição"`

**Hipótese**: query genérica; textual vai retornar qualquer artigo com
ambas as palavras (incluindo não-pertinentes). Semântico deve privilegiar
análises sobre aprendizagem cognitiva de fato.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 6 — Subtópico de nicho

**Query**: `"cognição incorporada e fenomenologia"`

**Hipótese**: poucos artigos têm esses termos exatos; busca semântica
deve surfaçar análises sobre embodied cognition, corporeidade, Merleau-Ponty.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 7 — Termos em variante ortográfica/dialectal

**Query**: `"análise cognitiva"`

**Hipótese**: query central da plataforma; ambos os modos devem ter alta
recall. Avaliar se semântico captura análises que não usam "análise cognitiva"
explicitamente mas tratam do mesmo objeto.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 8 — Autor específico (textual deve ganhar)

**Query**: `"Vygotsky"`

**Hipótese**: aqui a busca textual tem vantagem clara — o nome é específico
e insubstituível. Semântico pode poluir com resultados de outros autores
socioconstrutivistas. Documentar o caso onde textual é melhor.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 9 — Pergunta de pesquisa em linguagem natural

**Query**: `"qual a relação entre cognição e redes sociais científicas"`

**Hipótese**: a busca textual vai provavelmente retornar zero resultados
(muitos stopwords, frase não-usual). Semântico deve retornar análises
sobre redes de colaboração e cognição distribuída.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

### Query 10 — Epistemologia específica

**Query**: `"realismo crítico e análise cognitiva"`

**Hipótese**: ambos os modos; verificar se semântico recupera análises
classificadas com epistemologia "realismo" mesmo sem mencionar "realismo crítico".

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Análise**: _a preencher_

---

## Bloco C — Fronteira: teste de viés de canonicidade (específico da AnCo)

Estas queries usam **conceitos centrais de Teresinha Fróes** que raramente
aparecem com o rótulo "análise cognitiva" no corpus. São o teste do §0: o modelo
consegue **reconhecer obras de fronteira** que dialogam com a AnCo *sem usar o
vocabulário canônico*? Para cada uma, antes de rodar, **escolha à mão 1–2 obras
do acervo que você sabe serem pertinentes** (a "obra-alvo") e verifique se o
semântico as traz nos top-5. Se ele sistematicamente não as traz, há viés de
canonicidade — e a busca semântica **não pode** virar filtro de pertinência.

Para cada query: além da tabela top-5, marque **Obra-alvo no top-5 do semântico? (Sim/Não)**.

---

### Query C1 — Espiral do trabalho com o conhecimento

**Query**: `"produção, organização, acervação e difusão do conhecimento"`

**Conceito de Fróes**: a espiral produção → organização → **acervação** →
**difusão/socialização**. Termos como "acervação" quase não existem fora de Fróes.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

### Query C2 — Tradução do conhecimento

**Query**: `"tradução entre sistemas de saber científico tecnológico e mítico"`

**Conceito de Fróes**: **tradução do conhecimento** (tradução/transdução/
translocação entre sistemas de estruturação) — "processo-chave" da AnCo. Vocabulário
muito particular; teste forte de fronteira.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

### Query C3 — Comunidades epistêmicas e o comum

**Query**: `"comunidades que produzem conhecimento do privado ao público e ao comum"`

**Conceito de Fróes**: comunidades epistêmicas/cognitivas e o movimento
**privado → público → comum**. Testa se o modelo liga "comunidade científica",
"colaboração", "bem comum" ao horizonte da AnCo.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

### Query C4 — Dimensões que faltam na literatura

**Query**: `"dimensão ontológica, estética, afetiva e autopoiética do conhecer"`

**Conceito de Fróes**: as dimensões que a literatura **deixa de fora** (ética,
estética, afetiva, mítica, ontológica, autopoiética). Justamente o "antes
irreconhecido" — onde o viés de canonicidade mais provavelmente falha.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

### Query C5 — Compromisso ético-político

**Query**: `"superar a segregação sociocognitiva no acesso ao conhecimento"`

**Conceito de Fróes**: a **segregação sociocognitiva** como horizonte ético-político
do campo. Expressão própria da autora — quase ausente do vocabulário geral do modelo.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | — | | |
| 2 | — | | — | | |
| 3 | — | | — | | |
| 4 | — | | — | | |
| 5 | — | | — | | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

## Conclusões (a preencher após avaliação)

### Placar agregado

| Bloco | Queries | P@5 textual (média) | P@5 semântico (média) | Vencedor |
|-------|---------|---------------------|------------------------|----------|
| A–B (geral) | 1–10 | _ | _ | _ |
| C (fronteira) | C1–C5 | _ | _ | _ |

**Indicador de viés de canonicidade** — obras-alvo de fronteira nos top-5 do
semântico: **_ / 5** (ou _/N alvos). _Quanto mais baixo, maior o viés._

### Quando a busca semântica ganha
_a preencher_

### Quando a busca textual ganha
_a preencher_

### Veredito sobre o viés de fronteira (bloco C)
_a preencher — ex.: "o semântico trouxe X/5 obras-alvo; abaixo de 3/5 confirma que
a busca semântica deve permanecer só como descoberta, nunca como gate de pertinência"._

### Recomendação de modo padrão
_a preencher_

### Decisão sobre fine-tuning
_a preencher — só faz sentido se: (a) houver lacuna medida acima; (b) houver
conjunto de avaliação maduro; (c) o treino incluir deliberadamente obras de
fronteira, para corrigir e não reforçar o viés do bloco C. Ver discussão de
TSDAE/GPL × supervisionado com `sentence-transformers`._

### Observações sobre o modelo `paraphrase-multilingual-MiniLM-L12-v2`
_a preencher_

---

## Como executar a avaliação

```bash
# 1. Subir o container de embeddings
docker compose -f infra/docker-compose.yml --profile embeddings up -d embeddings

# 2. Aguardar o modelo carregar (~2-3 minutos na primeira vez)
docker compose -f infra/docker-compose.yml logs -f embeddings  # aguardar "Modelo pronto"

# 3. Indexar o acervo
docker compose -f infra/docker-compose.yml exec web python manage.py reindexar_embeddings

# 4. Comparar os dois modos na mesma query (trocar só o parâmetro modo):
#    https://anco.paulovicente.pro.br/acervo/?q=<query>&modo=textual
#    https://anco.paulovicente.pro.br/acervo/?q=<query>&modo=semantico
#    (o score 0-100% aparece ao lado de cada resultado no modo semântico)
```

> **Dica de preenchimento.** Faça o bloco C **primeiro escolhendo as obras-alvo**
> (o que você, conhecendo o acervo, sabe ser pertinente a cada conceito de Fróes)
> e só depois rode as buscas. Caso contrário a tendência é julgar pertinente o que
> o modelo trouxe — exatamente o viés que queremos medir, não herdar.
