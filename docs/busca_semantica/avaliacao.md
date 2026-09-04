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
   `docs/metodo/protocolo-anco-analise.md` §7). O **bloco C** testa exatamente isso.

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
| 1 | APHORISMS AS MEANS OF INTERPRETING OF LINGUISTIC TERMS: PE | | APHORISMS AS MEANS OF INTERPRETING OF LINGUISTIC TERMS: PE | 64% | |
| 2 | — | | The ubiquity of epistemics: A rebuttal to the 'epistemics | 63% | |
| 3 | — | | Análise discursiva sobre promoção da saúde no programa aca | 62% | |
| 4 | — | | Scientific popularization and media coverage of science Te | 61% | |
| 5 | — | | Thematic Scientific Bibliography as a Discourse: Modern Yo | 61% | |

**Análise**: _a preencher_

---

### Query 2 — Tradução entre línguas

**Query**: `"cognitive analysis of scientific literature"`

**Hipótese**: como o modelo é multilíngue, deve retornar análises sobre
cognição e literatura científica mesmo que estejam escritas em português.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | Cognitive literary studies: Theory, experiments, analyses | 82% | |
| 2 | — | | TRANSIÇÃO, PLASTICIDADE DE FRONTEIRAS E IDENTIDADE CIENTÍF | 75% | |
| 3 | — | | Thematic Scientific Bibliography as a Discourse: Modern Yo | 71% | |
| 4 | — | | On the rationality of decision-aiding processes | 69% | |
| 5 | — | | Teoría y metodología de investigación sobre libros de text | 69% | |

**Análise**: _a preencher_

---

### Query 3 — Conceito abstrato sem termos exatos

**Query**: `"como pesquisadores constroem conhecimento coletivo"`

**Hipótese**: texto conversacional sobre cognição social; busca textual
vai encontrar pouco. Busca semântica deve retornar análises sobre
cognição distribuída, cocriação científica, etc.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | Didactic-Pedagogical Approaches in e-Learning: Teaching Au | 66% | |
| 2 | — | | TESE: Análise conceitual e cognitiva: Modac - um modelo di | 63% | |
| 3 | — | | A relação entre a memória social e sociocognição: busca do | 63% | |
| 4 | — | | A REDE COMO ESPAÇO MULTIRREFERENCIAL DE APRENDIZAGEM. | 63% | |
| 5 | — | | TESE: ENCRUZILHADAS E LINHAS DE FUGA DA INTERATIVIDADE | 58% | |

**Análise**: _a preencher_

---

### Query 4 — Metodologia específica

**Query**: `"revisão sistemática de literatura"`

**Hipótese**: ambos os modos devem ter boa performance; avaliar se
semântico pega variantes como "mapeamento bibliométrico", "scoping review".

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | A SYSTEMATIC LITERATURE REVIEW ON 360° PANORAMIC APPLICATI | | Book Review: Patricia Canning, Style in the Renaissance: L | 72% | |
| 2 | — | | In search of a lost treasure: cultural mapping studies in | 60% | |
| 3 | — | | Beliefs and Practices Concerning Academic Writing Among Po | 59% | |
| 4 | — | | Thematic Scientific Bibliography as a Discourse: Modern Yo | 59% | |
| 5 | — | | ЯЗЫКОВАЯ РЕАЛИЗАЦИЯ АВТОРСКОЙ МОДАЛЬНОСТИ... // Language r | 59% | |

**Análise**: _a preencher_

---

### Query 5 — Área temática ampla

**Query**: `"educação e cognição"`

**Hipótese**: query genérica; textual vai retornar qualquer artigo com
ambas as palavras (incluindo não-pertinentes). Semântico deve privilegiar
análises sobre aprendizagem cognitiva de fato.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | Demandas cognitivas en tareas enviadas a preescolares dura | 77% | |
| 2 | — | | Design and Application of Computer-Aided College Chinese I | 73% | |
| 3 | — | | Análise cognitiva das tarefas de comparação de probabilida | 72% | |
| 4 | — | | Epistemic and Cognitive Analysis of a 2D Visualization Tas | 71% | |
| 5 | — | | Análise cognitiva de tarefas de comparação de probabilidad | 71% | |

**Análise**: _a preencher_

---

### Query 6 — Subtópico de nicho

**Query**: `"cognição incorporada e fenomenologia"`

**Hipótese**: poucos artigos têm esses termos exatos; busca semântica
deve surfaçar análises sobre embodied cognition, corporeidade, Merleau-Ponty.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | THE ANALYSIS OF CONCEPTS IN A TERMINOLOGY: A CASE STUDY OF | 78% | |
| 2 | — | | "Typical" and "imperceptible" as modus language category | 77% | |
| 3 | — | | Un análisis cognitivista de las perífrasis modales de obli | 77% | |
| 4 | — | | The Polysemy of Khilāl: A Cognitive Approach | 76% | |
| 5 | — | | Imagining the future self through thought experiments | 76% | |

**Análise**: _a preencher_

---

### Query 7 — Termos em variante ortográfica/dialectal

**Query**: `"análise cognitiva"`

**Hipótese**: query central da plataforma; ambos os modos devem ter alta
recall. Avaliar se semântico captura análises que não usam "análise cognitiva"
explicitamente mas tratam do mesmo objeto.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | Uma análise cognitivo-axiológica dos anúncios do Gymshark | | A PSYCHODIAGNOSTIC COGNITIVE ANALYSIS OF PERIODONTAL PATIE | 81% | |
| 2 | TESE - AnCo-REDES _ MODELO PARA ANÁLISE COGNITIVA COM BASE | | Un análisis cognitivista de las perífrasis modales de obli | 80% | |
| 3 | Linguo-cognitive analysis of a literary text: linguistic m | | The Polysemy of Khilāl: A Cognitive Approach | 80% | |
| 4 | TESE: Análise conceitual e cognitiva: Modac - um modelo di | | Cognitive literary studies: Theory, experiments, analyses | 80% | |
| 5 | Intelligent Algorithms of Processing of Information in the | | Scenario Modelling of the Green Economy in an Economic Spa | 76% | |

**Análise**: _a preencher_

---

### Query 8 — Autor específico (textual deve ganhar)

**Query**: `"Vygotsky"`

**Hipótese**: aqui a busca textual tem vantagem clara — o nome é específico
e insubstituível. Semântico pode poluir com resultados de outros autores
socioconstrutivistas. Documentar o caso onde textual é melhor.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | Presuntivismo e falsa contraposição entre mentira e verdad | 50% | |
| 2 | — | | Comportamento infocomunicacional de bibliotecários e estud | 41% | |
| 3 | — | | Articuler cognition spatiale et cognition environnementale | 41% | |
| 4 | — | | Expert cognition in the production sequence of Acheulian c | 41% | |
| 5 | — | | ANADIPLOSIS AS A MEANS OF COHESION: THE LOCATIVE-TEMPORAL | 40% | |

**Análise**: _a preencher_

---

### Query 9 — Pergunta de pesquisa em linguagem natural

**Query**: `"qual a relação entre cognição e redes sociais científicas"`

**Hipótese**: a busca textual vai provavelmente retornar zero resultados
(muitos stopwords, frase não-usual). Semântico deve retornar análises
sobre redes de colaboração e cognição distribuída.

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | A relação entre a memória social e sociocognição: busca do | 70% | |
| 2 | — | | Representações sociais de profissionais de emergência sobr | 68% | |
| 3 | — | | COGNIÇÃO EM AMBIENTES COM MEDIAÇÃO TELEMÁTICA... | 66% | |
| 4 | — | | Brain-Behavior Participant Similarity Networks among Youth | 66% | |
| 5 | — | | The Fundamentals of Cognitive Informatics | 66% | |

**Análise**: _a preencher_

---

### Query 10 — Epistemologia específica

**Query**: `"realismo crítico e análise cognitiva"`

**Hipótese**: ambos os modos; verificar se semântico recupera análises
classificadas com epistemologia "realismo" mesmo sem mencionar "realismo crítico".

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | Metaphorically redefined vocabulary: Categorization and sy | 62% | |
| 2 | — | | Theatre as research | 60% | |
| 3 | — | | Imagining the future self through thought experiments | 59% | |
| 4 | — | | Ritual and Christian Beginnings: A Socio-Cognitive Analysi | 59% | |
| 5 | — | | TRANSIÇÃO, PLASTICIDADE DE FRONTEIRAS E IDENTIDADE CIENTÍF | 57% | |

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
| 1 | — | | A relação entre a memória social e sociocognição: busca do | 64% | |
| 2 | — | | Didactic-Pedagogical Approaches in e-Learning: Teaching Au | 63% | |
| 3 | — | | Comportamento infocomunicacional de bibliotecários e estud | 62% | |
| 4 | — | | TESE: Análise conceitual e cognitiva: Modac - um modelo di | 61% | |
| 5 | — | | A REDE COMO ESPAÇO MULTIRREFERENCIAL DE APRENDIZAGEM. | 58% | |

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
| 1 | — | | The Fundamentals of Cognitive Informatics | 61% | |
| 2 | — | | Comportamento infocomunicacional de bibliotecários e estud | 58% | |
| 3 | — | | Trans/Form/Ação | 57% | |
| 4 | — | | TRANSIÇÃO, PLASTICIDADE DE FRONTEIRAS E IDENTIDADE CIENTÍF | 56% | |
| 5 | — | | Expert cognition in the production sequence of Acheulian c | 55% | |

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
| 1 | — | | Defining the community of interest as thematic and cogniti | 59% | |
| 2 | — | | A relação entre a memória social e sociocognição: busca do | 55% | |
| 3 | — | | TESE: ENCRUZILHADAS E LINHAS DE FUGA DA INTERATIVIDADE | 55% | |
| 4 | — | | Didactic-Pedagogical Approaches in e-Learning: Teaching Au | 54% | |
| 5 | — | | "Wish you were here" trust in public administration in Lat | 53% | |

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
| 1 | — | | Structural-semantic analysis of Mansi good wishes | 62% | |
| 2 | — | | "Typical" and "imperceptible" as modus language category | 62% | |
| 3 | — | | Address inversion in Swahili: Usage patterns, cognitive mo | 60% | |
| 4 | — | | When to Use Your Head and When to Use Your Heart: The Diff | 60% | |
| 5 | — | | A Multimodal Analysis of the Representation of Hegemonic M | 60% | |

**Obra-alvo no top-5 do semântico?** _Sim / Não_ · **Análise**: _a preencher_

---

### Query C5 — Compromisso ético-político

**Query**: `"superar a segregação sociocognitiva no acesso ao conhecimento"`

**Conceito de Fróes**: a **segregação sociocognitiva** como horizonte ético-político
do campo. Expressão própria da autora — quase ausente do vocabulário geral do modelo.

**Obra(s)-alvo escolhida(s)**: _a preencher_

| Rank | Modo textual | Pertinência | Modo semântico | Score | Pertinência |
|------|-------------|-------------|---------------|-------|-------------|
| 1 | — | | A relação entre a memória social e sociocognição: busca do | 71% | |
| 2 | — | | Didactic-Pedagogical Approaches in e-Learning: Teaching Au | 64% | |
| 3 | — | | Address inversion in Swahili: Usage patterns, cognitive mo | 61% | |
| 4 | — | | Linguistic and Cognitive Analysis of Inter-Cultural Busine | 60% | |
| 5 | — | | Cross-cultural competence of communicators as a way to cre | 59% | |

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

### Observações mecânicas (factuais — coletadas automaticamente, sem julgamento)

> Coletado em 2026-06 sobre 652 análises indexadas. São **fatos de recuperação**,
> não juízos de pertinência (esses são seus).

- **Modo textual retornou 0 resultados em 12 das 15 queries.** Só devolveu algo em
  Q1 (1), Q4 (1) e Q7 (5). Confirma que o FTS exige casamento de termos: perde toda
  pergunta em linguagem natural e todo o vocabulário próprio de Fróes.
- **O bloco C inteiro (C1–C5) deu 0 no textual** — nenhuma das expressões de
  fronteira ("acervação", "tradução do conhecimento", "segregação sociocognitiva"…)
  existe literalmente no corpus. É o cenário em que **só** a busca semântica opera.
- **O modo semântico sempre devolve 5 resultados** (ele retorna os mais próximos,
  mesmo quando a similaridade é baixa: no bloco C os scores caem a 53–64%, e em Q8
  "Vygotsky" a 40–50%). Score baixo é o sinal de que "o mais próximo" pode ainda
  ser irrelevante — **é exatamente aí que o seu julgamento decide**.
- Vários títulos se repetem entre queries diferentes (ex.: *"A relação entre a
  memória social e sociocognição"* aparece em Q3, Q9, C1, C3, C5). Pode indicar uma
  análise "central" no espaço vetorial — ou um viés de hub a investigar.

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

---

## Apêndice — Vizinhança semântica de "análise cognitiva" (sonda diagnóstica)

> **O que é.** Uma **sonda** da geometria do modelo: embutimos o termo "análise
> cognitiva" e uma lista de termos candidatos, e ordenamos por similaridade do
> cosseno. Não lê o banco vetorial (que guarda **documentos**, não termos) — usa o
> **mesmo modelo** para vetorizar termos soltos. Mede **o que o modelo pré-treinado
> "pensa"**, não o corpus. Coletado em 2026-06 com `paraphrase-multilingual-MiniLM-L12-v2`.

| Sim. | Termo | | Sim. | Termo |
|------|-------|---|------|-------|
| **98%** | cognitive analysis | | 56% | pensamento |
| 90% | cognitivo | | 52% | Neuroconstrutivismo |
| 90% | ciências cognitivas | | 50% | metacognição |
| 87% | cognição | | 49% | conhecimento |
| 85% | cognição incorporada | | 49% | análise do discurso |
| 85% | psicologia cognitiva | | 48% | **difusão do conhecimento** |
| 83% | neurociência cognitiva | | 47% | revisão sistemática |
| 74% | linguística cognitiva | | 39% | epistemologia |
| 71% | cognição distribuída | | **36%** | **tradução do conhecimento** |
| 68% | mente | | **34%** | **multirreferencialidade** |
| 66% | análise | | 33% | 🟥 futebol (controle) |
| 63% | cérebro | | 32% | Empirismo |
| 62% | inteligência artificial | | 26% | 🟥 gastronomia (controle) |
| | | | 16% | 🟥 economia agrícola (controle) |

**Leitura:**

1. **Multilíngue robusto** — "cognitive analysis" = 98% (PT≈EN no mesmo ponto).
2. **Ancoragem lexical** — o topo é todo da família "cognit-" (ciências/psicologia/
   neurociência cognitiva). O modelo mede muito a **semelhança de superfície** com o
   sentido de **ciência cognitiva anglo-saxã**.
3. **Evidência do viés de canonicidade** — os conceitos centrais da AnCo-Fróes ficam
   no rodapé: *tradução do conhecimento* (36%) e *multirreferencialidade* (34%) estão
   **à mesma distância que "futebol" (33%)**. Para o modelo, os pilares de Fróes são
   tão próximos de "análise cognitiva" quanto um esporte aleatório.

**Implicação.** Reforça que a busca semântica deve ser **descoberta, não gate de
pertinência**, no horizonte da AnCo. E define uma **métrica de progresso** para um
eventual fine-tuning: a meta seria ver "tradução do conhecimento"/"multirreferencialidade"
**subirem** do rodapé (34–36%) para perto do topo, sem que isso seja só reforço do
cluster "cognit-".

**Como reproduzir** (ajustar a lista `cands` conforme necessário):

```python
# manage.py shell
from apps.busca_semantica.embeddings import embed_texts
alvo = "análise cognitiva"
cands = ["cognição", "tradução do conhecimento", "multirreferencialidade",
         "difusão do conhecimento", "cognitive analysis", "futebol"]  # etc.
vecs = embed_texts([alvo] + cands)
av = vecs[0]
cos = lambda a, b: sum(x * y for x, y in zip(a, b))  # vetores normalizados
for sim, c in sorted(((cos(av, vecs[i + 1]), c) for i, c in enumerate(cands)), reverse=True):
    print(f"{round(sim * 100):3d}%  {c}")
```
