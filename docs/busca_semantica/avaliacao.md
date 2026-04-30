# Avaliação Qualitativa — Busca Semântica AnCo

> **Status**: rascunho pré-indexação.
>
> Este documento deve ser preenchido após `manage.py reindexar_embeddings` popular
> os 1.443 registros do acervo legado. As queries abaixo foram selecionadas para
> cobrir casos onde a busca semântica tem vantagem sobre a textual.
>
> **Modelo**: `paraphrase-multilingual-MiniLM-L12-v2` · 384 dimensões · ~420 MB RAM.

---

## Queries de avaliação (preencher após indexação)

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

## Conclusões (a preencher após avaliação)

### Quando a busca semântica ganha
_a preencher_

### Quando a busca textual ganha
_a preencher_

### Recomendação de modo padrão
_a preencher_

### Observações sobre o modelo `paraphrase-multilingual-MiniLM-L12-v2`
_a preencher_

---

## Como executar a avaliação

```bash
# 1. Subir o container de embeddings
docker compose --profile embeddings up -d embeddings

# 2. Aguardar o modelo carregar (~2-3 minutos na primeira vez)
docker compose logs -f embeddings  # aguardar "Modelo pronto"

# 3. Indexar o acervo
docker compose exec web python manage.py reindexar_embeddings

# 4. Acessar /acervo/?q=<query>&modo=semantico
#    e /acervo/?q=<query>&modo=textual para comparar
```
