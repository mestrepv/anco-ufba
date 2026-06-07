# Busca semântica na plataforma AnCo
### Como o sistema "entende" significado — e como isso serve à base AnCo

> Apresentação para **Profa. Teresinha Fróes** · Plataforma AnCo · 2026
>
> **Formato:** slides separados por `---`. Cada slide traz uma nota
> **🎤 Apresentador** com o roteiro de fala e o aprofundamento técnico.
> Os exemplos são **reais**, extraídos do acervo já indexado (652 análises).

---

## Slide 1 — A pergunta de fundo

> *"Como encontrar, num acervo crescente, as obras que **dialogam** com a Análise
> Cognitiva — mesmo quando elas não usam essas palavras?"*

A planilha (Forms → Sheets) só encontra o que **repete o termo**.
A AnCo, porém, é um campo **multirreferencial** e **emergente**: muita obra
trabalha com o conhecimento *sem* dizer "análise cognitiva".

**A busca semântica é uma tentativa de buscar por _significado_, não por _palavra_.**

> 🎤 **Apresentador:** Abra ancorando na experiência dela. A planilha era uma busca
> "literal": se a palavra não estava lá, a obra sumia. Mas o coração da AnCo é
> *reconhecer o antes irreconhecido* — obras dispersas, de outras áreas, que tocam o
> trabalho com o conhecimento sem usar o rótulo. Esse é exatamente o ponto cego de
> uma busca por palavra. A pergunta do slide é o fio de toda a apresentação.

---

## Slide 2 — Dois modos de buscar

```
   BUSCA TEXTUAL (palavra)              BUSCA SEMÂNTICA (significado)
   ───────────────────────             ─────────────────────────────
   "a palavra está no texto?"          "o sentido está próximo?"
   exata, literal, transparente        aproximada, por similaridade
   acha "cognição" só onde             acha obras parecidas mesmo
   está escrito "cognição"             com outras palavras
```

Na plataforma os dois convivem — um **botão** alterna textual ⇄ semântico.
Nenhum substitui o outro.

> 🎤 **Apresentador:** Deixe claro que **não trocamos uma pela outra**. A textual é
> precisa e auditável (bom para nome de autor, termo exato). A semântica é
> exploratória (bom para descobrir o disperso). O usuário escolhe no botão. Mais à
> frente mostro um caso real onde a textual devolve **zero** e a semântica acha
> obras pertinentes — e outro onde a textual é melhor.

---

## Slide 3 — A ideia central: significado vira "coordenada"

Um modelo de IA lê um texto e devolve uma **lista de números** — um ponto num
"mapa de significados". Textos com sentido próximo caem **perto**.

```
        MAPA DE SIGNIFICADOS (intuição em 2 dimensões)

   cognição ●      ● análise cognitiva
              ● psicologia cognitiva
        ● mente        ● ciências cognitivas
                                                  ● difusão do
                                                    conhecimento
                          ● epistemologia
                                              ● tradução do
              ● futebol ✕                       conhecimento
```

> 🎤 **Apresentador:** Esta é a metáfora-chave — gaste tempo aqui. Cada obra/termo
> vira um *ponto* num mapa. "Perto" = sentido parecido; "longe" = sentido diferente.
> O mapa real não tem 2 dimensões, tem **384** (não dá para desenhar), mas a
> intuição é essa. Avise que as posições deste slide são **ilustrativas** — no
> Slide 9 mostro as distâncias **medidas de verdade**, e elas trazem uma surpresa
> importante para a AnCo.

---

## Slide 4 — De onde vêm os números (o "tradutor")

```
   texto da obra            modelo de IA              vetor (384 números)
   ─────────────            ────────────              ───────────────────
   "Estudo da         ──►   transformador     ──►     [0.12, -0.04, 0.88,
    cognição em              de frases                  0.31, ... , -0.07]
    leitores..."            (sentence-transformer)     = a "coordenada"
```

- Modelo: **`paraphrase-multilingual-MiniLM-L12-v2`** — aberto, gratuito, **multilíngue**.
- Roda **no nosso servidor** — sem nuvem paga, sem enviar os dados para fora.
- Foi treinado por terceiros (Microsoft + grupo acadêmico de Darmstadt) em **texto geral**.

> 🎤 **Apresentador:** Três pontos a frisar: (1) é o mesmo "tradutor" para toda obra
> e para toda busca — por isso os pontos são comparáveis. (2) É **local e gratuito**
> — coerente com a economia de um projeto acadêmico e com a privacidade do acervo.
> (3) Guarde a frase "treinado em **texto geral**" — ela explica a limitação do
> Slide 9: o modelo nunca leu Fróes; aprendeu o sentido comum das palavras.

---

## Slide 5 — Como uma busca acontece

```
   1. você digita        "como pesquisadores constroem conhecimento coletivo"
                                          │
   2. o modelo           vira um vetor (a coordenada da sua pergunta)
                                          │
   3. o banco compara    mede a distância até CADA obra do acervo
      (PostgreSQL +                       │
       extensão pgvector)                 ▼
   4. resposta           as obras MAIS PRÓXIMAS, com % de similaridade
```

O banco de dados ganhou uma "peça extra" (**pgvector**) que sabe **medir
distância entre vetores** — algo que um banco comum não faz.

> 🎤 **Apresentador:** Conecte com algo que ela conhece: indexação. Aqui o "índice"
> não é por palavra, é por **posição no mapa de significados**. O banco percorre as
> 652 obras, mede a distância de cada uma à pergunta, e devolve as mais próximas com
> um percentual. O "% de similaridade" que aparece na tela é essa distância
> convertida: 100% = idêntico, valores baixos = "o mais próximo, mas ainda longe".

---

## Slide 6 — Exemplo real ①: pergunta em linguagem natural

**Busca:** *"qual a relação entre cognição e redes sociais científicas"*

```
   MODO TEXTUAL      →   0 resultados   (a frase não casa literalmente)
   MODO SEMÂNTICO    →   70%  "A relação entre memória social e sociocognição..."
                         68%  "Representações sociais de profissionais..."
                         66%  "Cognição em ambientes com mediação telemática..."
```

A busca por palavra **não acha nada**; a semântica recupera obras pertinentes.

> 🎤 **Apresentador:** Este é o "momento aha". Uma pergunta escrita como gente fala
> derruba a busca literal (zero). A semântica entende a *intenção* e traz obras sobre
> cognição social e redes. Diga que, no nosso teste, **a textual deu zero em 12 das
> 15 buscas** desse tipo — é a maior fraqueza dela e a maior força da semântica.

---

## Slide 7 — Exemplo real ②: atravessando idiomas

**Busca (em português):** *"cognitive analysis of scientific literature"*

```
   MODO SEMÂNTICO →   82%  "Cognitive literary studies: Theory, experiments..."
                      75%  "TRANSIÇÃO, PLASTICIDADE DE FRONTEIRAS..." (PT)
                      71%  "Thematic Scientific Bibliography as a Discourse"
```

O modelo é **multilíngue**: uma busca traz obras em **português e inglês**
sobre o mesmo sentido, sem tradução manual.

> 🎤 **Apresentador:** Para um acervo bilíngue, isto é ouro. O significado mora num
> mapa **independente do idioma** — "cognição" (PT) e "cognition" (EN) caem quase no
> mesmo ponto. Uma busca alcança as duas literaturas de uma vez. No nosso teste,
> "análise cognitiva" e "cognitive analysis" ficaram a **98%** de similaridade.

---

## Slide 8 — Para que serve à base AnCo

- **Reconhecer o disperso** — aproxima obras de áreas distintas que tratam do
  trabalho com o conhecimento, ainda que não usem o termo. *(o ethos da AnCo)*
- **Apoiar a triagem** — ajuda a *encontrar candidatos* a incluir, mais rápido.
- **Acervo bilíngue** — uma busca cobre PT e EN.
- **Perguntas em linguagem natural** — o pesquisador pergunta como pensa.

> 🎤 **Apresentador:** Amarre na missão. A AnCo quer *reconhecer o antes
> irreconhecido*; a busca semântica é uma **lanterna** que ajuda a achar o que a
> busca literal escondia. Mas — e este é o gancho para o próximo slide — lanterna
> **ilumina, não decide**. Ela sugere candidatos; quem julga pertinência é o humano.

---

## Slide 9 — O limite honesto (e ele importa para a AnCo)

**Medimos** quais termos o modelo coloca perto de "análise cognitiva":

```
   PERTO (o modelo associa forte)        LONGE (o modelo associa fraco)
   ──────────────────────────────        ──────────────────────────────
   98%  cognitive analysis               48%  difusão do conhecimento
   90%  ciências cognitivas              36%  tradução do conhecimento   ◄┐
   87%  cognição                         34%  multirreferencialidade     ◄┤
   85%  psicologia cognitiva             33%  futebol (controle!)         │
                                                                          │
            conceitos centrais de Fróes ──────────────────────────────────┘
            estão tão "longe" quanto futebol
```

O modelo entende "análise cognitiva" como a **ciência cognitiva mainstream** —
não como o **campo multirreferencial do trabalho com o conhecimento**.

> 🎤 **Apresentador:** Slide mais delicado e mais importante. Seja transparente: o
> modelo aprendeu o sentido **comum** das palavras (Slide 4), não a obra de Fróes.
> Por isso ele cola no morfema "cognit-" e deixa *tradução do conhecimento*,
> *multirreferencialidade*, *difusão* lá no rodapé — à mesma distância que
> "futebol". Não é defeito de instalação; é o **viés de um modelo geral**. Para a
> AnCo isso é crucial: a ferramenta tende a **sub-representar exatamente as obras de
> fronteira** que o campo quer valorizar. Reconhecer isso é o que dá credibilidade
> científica ao uso da ferramenta.

---

## Slide 10 — O princípio: a IA é lanterna, não juiz

```
   A IA pode...                      A IA NÃO faz...
   ───────────                       ───────────────
   ✓ ajudar a ACHAR candidatos       ✗ decidir pertinência
   ✓ aproximar obras por sentido     ✗ preencher a análise
   ✓ cruzar idiomas                  ✗ sugerir revisores
   ✓ aceitar perguntas naturais      ✗ escrever resenhas

           ────────────  QUEM JULGA É O HUMANO  ────────────
        triagem por ≥2 revisores · curadoria · Matriz AnCo
```

Decisão registrada na especificação: *embeddings são **acesso à informação, não
produção de análise***.

> 🎤 **Apresentador:** Este é o compromisso ético-metodológico, e ele responde
> diretamente ao limite do Slide 9. Justamente **porque** o modelo tem viés, ele
> nunca recebe poder de decisão. Ele ilumina a sala; quem reconhece o valor de cada
> obra é o pesquisador, pela Matriz. A tecnologia serve à metodologia, não o
> contrário — e isso protege a pluralidade que a AnCo defende.

---

## Slide 11 — O que isso abre para o futuro

1. **Medir antes de confiar** — protocolo de avaliação já pronto (`avaliacao.md`),
   com um bloco de **consultas de fronteira** (conceitos de Fróes).
2. **Talvez ensinar o modelo a AnCo** — é possível **ajustar** (fine-tuning) o
   modelo com a própria base, para aproximar *tradução do conhecimento* &
   *multirreferencialidade* do centro — **se** a medição justificar.
3. **Cuidado declarado** — um ajuste mal-feito poderia *reforçar* o viés; por isso,
   primeiro medir, depois decidir, sempre incluindo as obras de fronteira.

> 🎤 **Apresentador:** Termine olhando para frente, mas com sobriedade. Não
> prometemos que a IA "entenderá Fróes" hoje — mostramos que (a) sabemos medir o
> quanto ela entende, e (b) há um caminho técnico para ensiná-la, se valer a pena. A
> decisão é da equipe, baseada em evidência, não em entusiasmo. Convide-a a opinar
> sobre **quais conceitos de Fróes** deveriam guiar essa avaliação.

---

## Slide 12 — Síntese

> A busca semântica transforma **significado em coordenada**, encontra obras
> **próximas em sentido** (em vários idiomas, por perguntas naturais) e amplia a
> capacidade de **reconhecer o disperso** — o ethos da AnCo.
>
> Ela é **lanterna, não juiz**: ilumina candidatos; **o reconhecimento é humano**.
>
> E sabemos, com número, onde ela ainda **não** enxerga os conceitos de Fróes —
> ponto de partida honesto para evoluí-la.

**Obrigado.** · Perguntas?

> 🎤 **Apresentador:** Feche repetindo as três ideias: significado-vira-coordenada;
> lanterna-não-juiz; medimos-o-viés-com-honestidade. Se houver tempo, ofereça uma
> demonstração ao vivo: abrir o acervo, buscar a mesma frase nos dois modos e
> mostrar a diferença na tela.

---

## Anexo para o apresentador — perguntas prováveis

- **"A IA vai escolher os artigos por nós?"** Não. Ela só ajuda a *achar*; a inclusão
  passa por ≥2 revisores e curadoria (Slide 10).
- **"E se ela errar / tiver viés?"** Tem viés, e nós o **medimos** (Slide 9). Por isso
  ela não decide nada — é exatamente a salvaguarda.
- **"Custa caro? Manda nossos dados para fora?"** Não. Modelo aberto, roda no nosso
  servidor, sem custo recorrente e sem enviar dados a terceiros (Slide 4).
- **"Por que não usar uma IA 'famosa' (ChatGPT)?"** Custo recorrente, dependência
  externa e privacidade. Para *acesso à informação*, o modelo local basta — e
  mantemos o controle metodológico.
- **"Isso substitui a Matriz?"** De forma alguma. A Matriz é o juízo interpretativo;
  a busca é só a porta de entrada para encontrar o que analisar.
