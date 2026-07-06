# Proposta — Evolução da Matriz AnCo para fidelidade conceitual a Fróes Burnham

> **Status:** proposta para apreciação das coordenadoras (Profa. Teresinha Fróes /
> Profa. Leliana). Nada aqui foi implementado. Complementa o
> `docs/protocolo-anco-analise.md` (§7, "o que a Matriz ainda não captura") e o
> `PARECER_plataforma_x_proposta_Froes.md` (§6).
>
> **Fontes primárias cotejadas:** os dois capítulos de Fróes Burnham —
> *Análise cognitiva, um campo multirreferencial do conhecimento? Aproximações
> iniciais para sua construção* e *Análise cognitiva reconhecendo o antes
> irreconhecido* (+ *Abordagens epistemológicas da cognição*, com Lage e
> Michinel).

---

## 1. Motivação

A Matriz atual cobre bem a leitura **epistemológico-estrutural** das obras
(objeto, objetivo, foco, metodologia, epistemologia, teoria, referenciais,
resultados) e a **prospecção do termo** (presença, pertinência, definição). Mas
os conceitos que estruturam a concepção madura de AnCo em Fróes (2010/2012)
**não têm campo próprio** — hoje só cabem em texto livre (*Aspectos
relevantes*/*Observações*), onde **não são agregáveis**.

O risco de não evoluir: a própria Fróes diagnostica que a literatura do campo
carece de explicitação de fundamentos e **silencia sobre as dimensões ética,
estética, afetiva, mítica, ontológica e autopoiética**. Se a Matriz não tiver
onde registrar essas dimensões, o acervo vai "confirmar" a ausência delas —
**reproduzindo a lacuna que o campo quer corrigir**.

O ganho de evoluir: cada conceito de Fróes vira **variável mensurável do
acervo**. A plataforma deixa de só *organizar* o trabalho do grupo e passa a
*fundamentar* o campo — produzindo evidência empírica do estatuto
epistemológico proposto desde 2010 (ex.: "de N obras analisadas, X% operam só
na fase de produção da espiral; Y% não tocam nenhuma dimensão ética/estética/
afetiva").

## 2. Princípios da evolução (inegociáveis)

1. **Aditiva.** Nenhum campo existente muda de nome, tipo ou semântica. Nenhuma
   análise existente (rascunho, publicada ou legado) é invalidada ou reaberta.
2. **Opcional na largada.** Os campos novos **não entram** no checklist de
   submissão (`campos_faltantes_submissao`) na primeira fase. Promover algum a
   obrigatório é decisão posterior das coordenadoras, com base no uso real.
3. **Acervo legado intocado.** Análises `legado` nunca são retro-preenchidas
   automaticamente; ficam com os campos novos vazios ("não aferido"), que é
   diferente de "ausente na obra".
4. **Vocabulário controlado onde houver agregação.** Segue o padrão já existente
   (`Vocabulario`/`TermoVocabulario` + M2M com `limit_choices_to`), para que os
   novos eixos sejam consultáveis e mapeáveis como epistemologia/teoria já são.
5. **Vazio ≠ Não.** Em todos os eixos novos, campo em branco significa "o
   analista não aferiu", nunca "a obra não mobiliza". (Mesma lógica do
   `BooleanField(null=True)` das presenças.)

## 3. Os cinco eixos novos

### Eixo A — Espiral do trabalho com o conhecimento

**Fundamento.** Para Fróes, a espiral **produção → organização → acervação →
difusão/socialização** é o esqueleto do trabalho com o conhecimento; os
processos "não se fecham em ciclos completos, mas ocorrem em movimentos
abertos" (*Aproximações*, §1). Perguntar em que fase(s) a obra opera é a
primeira leitura propriamente AnCo de qualquer obra.

**Proposta.** Campo M2M `espiral` → vocabulário novo `espiral`, com 4 termos
fixos semeados:

| Termo | Descrição curta (ajuda no editor) |
|---|---|
| Produção | A obra estuda/realiza a construção de conhecimento |
| Organização | …a estruturação (léxicos, taxonomias, ontologias, sistemas) |
| Acervação | …o registro, guarda e recuperação (acervos, bases, memória) |
| Difusão/Socialização | …a circulação, tradução e publicização |

Multisseleção (uma obra pode operar em várias fases). Sem "outro": a espiral é
taxonomia fechada da autora.

### Eixo B — Tradução do conhecimento (TC)

**Fundamento.** "Processo-chave" da AnCo (*Aproximações*, seção homônima).
Fróes distingue três operações: **tradução** (língua/linguagem → outra),
**transdução** (forma de representação → outra: verbal→icônica→sonora…),
**translocação** (conteúdo de um espaço/sistema de produção → outro).

**Proposta.** Campo M2M `traducao` → vocabulário novo `traducao`, com os 3
termos acima; + campo texto opcional `traducao_descricao` ("entre quais
sistemas/linguagens a obra traduz?"). Multisseleção.

### Eixo C — Comunidades e movimento do conhecimento

**Fundamento.** A AnCo estuda como **comunidades epistêmicas** (produção
normatizada e validada por pares — Haas, Knorr-Cetina) e **comunidades
cognitivas** (saber-fazer tácito das práticas — Wenger/Lave, Hussler & Rondé)
produzem/usam conhecimento, no movimento **privado → público → comum**
(Fróes/Ziman/Maffesoli).

**Proposta.** Dois campos M2M para o mesmo vocabulário novo `comunidade`:

- `comunidade_produtora` — que tipo de comunidade **produz** o conhecimento de
  que a obra trata;
- `comunidade_destinataria` — a que comunidade a obra **destina/socializa**
  esse conhecimento.

Termos iniciais (sujeitos à validação das professoras — ver §6):

| Termo | Exemplo |
|---|---|
| Comunidade epistêmica — científica | grupo de pesquisa, disciplina |
| Comunidade epistêmica — outra | legisladores, formuladores de política |
| Comunidade cognitiva — de prática | professores, profissionais de saúde |
| Comunidade cognitiva — profissional | trabalhadores de software, executivos |
| Comunidade cognitiva — tradicional | saberes tradicionais/locais |
| Comunidade ampliada / público geral | socialização stricto sensu |

### Eixo D — Dimensões mobilizadas

**Fundamento.** A concepção de 2012 define a AnCo como campo "que inclui
dimensões entretecidas de caráter teórico, epistemológico, metodológico,
**ontológico, axiológico, ético, estético, afetivo e autopoiético**" — e o
diagnóstico do capítulo é que a literatura quase não toca as últimas. Este é o
eixo com maior potencial de resultado empírico original.

**Proposta.** Campo M2M `dimensoes` → vocabulário novo `dimensao`:

| Termo |
|---|
| Ética |
| Estética |
| Afetiva/Emocional |
| Mítica/Religiosa |
| Ontológica |
| Autopoiética |
| Axiológica |

> **Nota de desenho:** as dimensões teórica/epistemológica/metodológica ficam
> **fora** deste vocabulário — já são capturadas pelos campos estruturais da
> aba 3. Este eixo marca exatamente as dimensões que Fróes aponta como
> **ausentes** na literatura, para que a ausência vire dado.

### Eixo E — Compromisso ético-político

**Fundamento.** O horizonte declarado do campo: "superação da **segregação
sociocognitiva** a que vêm sendo historicamente submetidas amplas faixas da
população" (*Aproximações*, conclusão).

**Proposta.** Par de campos no padrão pertinência/definição já existente:

- `compromisso_sociopolitico` — `BooleanField(null=True)`: "A obra explicita um
  compromisso com a socialização/democratização do conhecimento?"
- `compromisso_descricao` — `TextField(blank=True)`: como esse compromisso se
  expressa (obrigatório apenas se o anterior for Sim, espelhando a regra
  `define_conceito`/`definicao_extraida`).

## 4. Onde os eixos entram no editor (UX)

Nova **seção dentro da aba 3** (não uma aba nova), intitulada **"Trabalho com o
conhecimento (leitura AnCo)"**, posicionada após *Resultados* e antes de
*Contexto de produção*. Racional:

- manter 4 abas preserva o fluxo já conhecido dos analistas;
- os eixos são leituras analíticas da obra — pertencem à "Análise do artigo";
- a seção ganha um texto introdutório de 2 linhas + link para o protocolo
  (quando este for embutido no editor, pendência já registrada).

Cada campo novo leva *help text* de 1 frase extraída do protocolo. Os M2M usam
o mesmo componente de busca-e-seleção de epistemologia/teoria.

## 5. Plano de implementação (aditivo, 3 passos)

**Passo 1 — dados.** Migration de schema: 6 campos novos em `Analise` (4 M2M +
1 boolean nullable + 2 textos), todos `blank=True`/`null=True`. Migration de
dados: cria os 4 vocabulários (`espiral`, `traducao`, `comunidade`, `dimensao`)
e semeia os termos dos quadros acima. Reversível; zero alteração em linhas
existentes.

**Passo 2 — editor + protocolo.** Formulário/template da aba 3 com a nova
seção; `campos_faltantes_submissao()` **não muda** (exceto a regra condicional
compromisso Sim → descrição obrigatória); §7 do protocolo é reescrito: os eixos
saem de "limites" e viram instrução de preenchimento.

**Passo 3 — leitura agregada.** Incluir os eixos novos: (a) na página pública
da análise; (b) nas estatísticas do projeto (`/anco/p/<slug>/`), com contagens
por fase da espiral e por dimensão; (c) no texto dos embeddings (Fase 8), para
que a busca semântica os considere. Análises já publicadas seguem válidas; um
aviso discreto no editor ("há campos novos opcionais") convida — sem obrigar —
os autores a complementar.

**Fora do escopo desta proposta:** obrigatoriedade dos campos novos; qualquer
mudança no fluxo de curadoria/resenha; re-análise do legado.

## 6. Decisões que pertencem às coordenadoras

1. **Taxonomia de comunidades (Eixo C):** a tipologia proposta tem grão certo?
   Fróes menciona ainda comunidades religiosas, políticas, laborais — valem
   termos próprios ou entram como sinônimos dos existentes?
2. **Nomenclatura:** "Acervação" ou "Acervo"? "Difusão/Socialização" junto ou
   separado? Os textos usam as duas formas.
3. **Axiológica** como termo separado de Ética (a definição de 2012 lista
   ambas) ou fundir?
4. **Obrigatoriedade futura:** após um ciclo de uso (ex.: o piloto), quais
   eixos passam ao checklist de submissão? Sugestão: começar promovendo apenas
   a **espiral** (leitura mais básica e menos ambígua).
5. **Retro-preenchimento assistido:** quando houver volume, a busca semântica
   pode sugerir eixos para análises antigas a partir de *Aspectos relevantes*/
   *Observações* — sempre como sugestão a confirmar pelo autor, nunca
   automático. Aprovam a ideia em princípio?

## 7. Resumo em uma tabela

| Eixo | Conceito de Fróes | Campo(s) novo(s) | Tipo | Obrigatório? |
|---|---|---|---|---|
| A | Espiral do trabalho c/ conhecimento | `espiral` | M2M vocab `espiral` (4 termos) | não (candidato futuro) |
| B | Tradução do conhecimento | `traducao` + `traducao_descricao` | M2M vocab `traducao` (3) + texto | não |
| C | Comunidades epistêmicas/cognitivas | `comunidade_produtora`, `comunidade_destinataria` | 2× M2M vocab `comunidade` (~6) | não |
| D | Dimensões ausentes na literatura | `dimensoes` | M2M vocab `dimensao` (7) | não |
| E | Segregação sociocognitiva | `compromisso_sociopolitico` + `compromisso_descricao` | bool nulo + texto | condicional (Sim → descrição) |

---

## Anexo técnico (para a implementação, após aprovação)

- **Modelo** (`apps/acervo/models.py`, classe `Analise`): os 4 M2M seguem o
  padrão de `epistemologia`/`teoria` (`limit_choices_to={"vocabulario__codigo":
  "<codigo>"}`, `related_name="analises_por_<eixo>"`). O par booleano+texto
  segue `define_conceito`/`definicao_extraida`.
- **Checklist** (`Analise.campos_faltantes_submissao`, models.py): única
  mudança é a regra condicional do Eixo E, análoga à linha da definição
  extraída.
- **Vocabulários**: semeados por data migration com `Vocabulario.codigo` =
  `espiral|traducao|comunidade|dimensao`; termos com `descricao` preenchida
  (vira tooltip). Curadores podem acrescentar termos pelo admin, como hoje.
- **Histórico**: `django-simple-history` cobre os campos escalares
  automaticamente; conferir tracking dos novos M2M.
- **Embeddings** (Fase 8): incluir os rótulos dos eixos no texto embarcado e
  recalcular via comando existente.
- **Testes**: validação de modelo (regra condicional E), form da aba 3,
  idempotência da migration de seed — áreas obrigatórias conforme CLAUDE.md §6.
- **Commits**: `feat(vocabulario): adiciona vocabulários dos eixos Fróes`,
  `feat(acervo): campos da leitura AnCo na Matriz`, `feat(acervo): seção
  "Trabalho com o conhecimento" no editor`, `docs(protocolo): eixos Fróes
  deixam §7 e viram instrução`.
