# Auditoria de qualidade — base referencial AnCo

**Arquivo analisado**: `dados/legado/base-referencial-original.json`
**Total de registros**: 1.443
**Total de campos por registro**: 40
**Geração**: 2026-04-30
**Origem**: dump do Google Forms preenchido por estudantes de doutorado
seguindo as orientações de `docs/metodo/tutorial-base-anco.md`.

Este relatório complementa `docs/migracao/analise_legado.md` (focado em
estratégia do migrador). Aqui o foco é a **qualidade do dado bruto** do
ponto de vista do curador, com proposta de normalização para cada
problema encontrado.

---

## 1. Sumário executivo

Os números abaixo são contagens, não percentuais — um mesmo registro
pode aparecer em mais de uma categoria.

| Tipo de problema | Reg. afetados | Severidade |
|---|---:|---|
| **DOI canônico ok (`10.x/y`)** | 581 / 1.443 | — |
| **DOI fora do formato canônico** (ver §2) | 862 / 1.443 | alta |
| ↳ vazio ou `-` | 121 | média |
| ↳ DOI com barra `/` apagada (Excel) | 158 | **crítica** |
| ↳ ISBN convertido para notação científica | 48 | **crítica** |
| ↳ ISSN no campo DOI (puro + com prefixo "ISSN ") | 84 | alta |
| ↳ URL completa (`https://doi.org/...`, `doi.org/...`) | 208 | baixa (corrigível) |
| ↳ prefixo `DOI:`/`DOI`/`:` ou número de citação | 62 | baixa |
| ↳ múltiplos DOIs no mesmo campo (`;` separator) | 31 | média |
| ↳ ID Scopus (`2-s2.0-...`) ou Redalyc (`id=...`) | 15 | média |
| ↳ "Não consta", "Não tem", texto descritivo | 14 | média |
| ↳ número de ordem do item no lugar do DOI | 59 | alta |
| ↳ ISBN puro (livro, não artigo) | 10 | média |
| ↳ ISBN + DOI grudados (`ISBN xxx / https://doi.org/...`) | 2 | média |
| ↳ DOI faltando dígito inicial (`0.1016/...` em vez de `10.`) | 2 | média |
| ↳ DOI com vírgulas-de-milhar (Excel formatou número) | 5 | média |
| ↳ só número grande (DOI sem prefixo `10.` nem barras) | 24 | alta |
| ↳ outros lixos textuais (citação completa, bibtex, …) | 21 | média |
| **Resumos idênticos em registros diferentes** | 603 | alta |
| **Multi-análise legítima ou ambígua** (§3) | 595 | informativo |
| **Suspeita de duplicata (mesmo título + analista vazio)** | 256 grupos | alta |
| **Duplicata REAL (mesmo artigo + mesmo analista)** | 6 grupos / 12 reg. | alta |
| **Variantes de grafia de Analista** | 10 grupos | média |
| **Texto inválido no campo Analista** (título do artigo, etc.) | 3 | alta |
| **Apenas 1 nome no campo Analista** | 5 grupos / 20 reg. | média |
| **Co-autoria em um único campo Analista** | 3 reg. | média |
| **Pagina_Final < Pagina_Inicial** | 3 | média |
| **Ano fora da janela 1900–2026** | 4 | alta |
| **Título tudo em CAIXA ALTA** | 149 | baixa |
| **Título vazio** | 13 | alta |
| **Resumo vazio** | 62 | média |
| **Resumo suspeitamente curto (<100 chars)** | 24 | alta |
| **Espaços duplicados em campos textuais** | 262 | baixa |
| **Tabs no meio do texto** | 95 | baixa |
| **NBSP / zero-width / BOM em texto** | 43 | baixa |
| **Variantes de capitalização em `Base_de_Consulta`** | 4 | baixa |
| **`Pertinencia_para_Area` com texto longo** | 22 | média |
| **`Presenca_AC_*` com 8+ valores não-booleanos cada** | ~60 | baixa |

**Encoding (mojibake `Ã£`/`Ã©`/etc.) não foi detectado** — o JSON está
em UTF-8 limpo. ✅

---

## 2. Campo `Numero_DOI`

O campo é o mais problemático da base. **Apenas 581 registros (40%)
estão no formato canônico** `10.xxxx/yyyy`. Os outros 862 precisam de
algum tratamento. As categorias se dividem assim:

### 2.1. Vazio ou `-` (121 registros)

Registros sem DOI declarado. Linhas: 66–73, 95+ outras.
**Proposta**: gerar identificador interno determinístico
`legacy:HASH(titulo|ano|periodico)` para preservar citabilidade.
(Estratégia já implementada no migrador da Fase 1.)

### 2.2. DOI com a barra `/` apagada — **158 registros**

Causa provável: Excel ou Sheets interpretou o DOI como número/data e
removeu a barra ao formatar. O sufixo numérico pode ter sido **grudado**
no prefixo, perdendo a separação original.

Exemplos:
- linha 75: `'101016'` → provavelmente `10.1016/...` mas o sufixo se perdeu
- linha 322: `'10117717456916177394'` → provavelmente `10.1177/1745691617739394`
- linha 333: `'101142021800141950006'` → provavelmente `10.1142/S0218001419500064`
- linha 354: `'01539020187504'` → fragmento sem prefixo `10.`

**Proposta**: na maioria dos casos com sufixo grudado é possível
recuperar o DOI tentando inserir a barra após `10.NNNN`. Para os casos
só-prefixo (`'101016'`), o DOI está irrecuperável a partir desse campo
— precisa ser refeito a partir do título do artigo (busca no Crossref).

### 2.3. ISBN convertido para notação científica — **48 registros** ⚠

O Excel converteu ISBNs (números de 13 dígitos começando com `978`) em
notação científica e gravou nessa forma. Exemplos:
- linha 18: `'9.78E+12'` → ISBN `978............` (precisão perdida)
- linha 303: `'1.01177E+19'` → era na verdade um DOI longo
  `10.1177/1xxxxxxxxxxxxxx` (também perdida precisão)
- linha 305: `'1.01142E+20'`, linha 308: `'1.01177E+21'`, …

**Proposta**: estes registros **não são recuperáveis automaticamente**.
A precisão se perdeu na exportação do Sheets. Para corrigir, é preciso:
1. Voltar à fonte original (PDF ou link de acesso) e re-extrair o DOI;
2. Marcar esses 48 registros para revisão manual.
**Lição**: estes são artefatos exclusivos da combinação Google Forms
+ Sheets — o sistema novo (digitação direta do DOI + lookup no
Crossref) não passa por planilha e não reproduz este erro (ver §8).

### 2.4. ISSN no campo DOI — **84 registros (somando 3 formas)**

ISSN identifica o **periódico**, não o **artigo**, então não substitui
o DOI.

| Forma | Reg. | Exemplos |
|---|---:|---|
| ISSN puro `0001-6918` | 31 | linhas 2, 91–96, 113… |
| `ISSN xxxx-yyyy` ou `ISSN: xxxx-yyyy` | 53 | linhas 141–183, 970, 1142, 1177… |

**Proposta**: criar coluna `ISSN` separada, mover o valor pra ela e
deixar `Numero_DOI` vazio (ou gerar `legacy:HASH`).

### 2.5. URL em vez de DOI canônico — **208 registros**

Formas detectadas:
- `https://doi.org/10.xxxx/yyy` (≈190)
- `http://dx.doi.org/10.xxxx/yyy` (poucos)
- `doi.org/10.xxxx/yyy` sem `https://` (8)

Exemplos: linhas 133, 631, 691, 701, 703, 736, 737, 740, 754…

**Proposta**: extração automatizável via regex
`r'10\.\d{3,9}/\S+'`. Stripar prefixos `https://(dx\.)?doi\.org/`.

### 2.6. Prefixo textual — **62 registros**

| Forma | Reg. |
|---|---:|
| `DOI: 10.xxxx/yyy` | 50 |
| `DOI10.xxxx/yyy` (sem dois-pontos) | 4 |
| `: 10.xxxx/yyy` | 2 |
| `1317 DOI: 10.xxxx/yyy` (número de citação grudado) | 2 |
| outros | 2 |

Exemplos: linhas 4, 5, 65, 754, 1264, 1397, 1416, 1439, 1441.

**Proposta**: regex de strip
`re.sub(r'^.*?(10\.\d{3,9}/\S+).*$', r'\1', v)`.

### 2.7. Múltiplos DOIs no mesmo campo — **31 registros**

Forma típica: `2-s2.0-85007337790 ; 10.1007/978-3-319-50901-3_56`
(ID Scopus + DOI, separados por `;`). Exemplos: linhas 32, 33, 34, 37,
38, 39, 42…

**Proposta**: separar pelo `;`, preservar o `10.x/y` como DOI canônico
e mover o ID Scopus para uma coluna `id_scopus` (opcional).

### 2.8. ID Scopus ou Redalyc puro — **15 registros**

- `2-s2.0-85018775281` (Scopus): 11 reg., linhas 35, 36, 40, 41…
- `id=14023076011` (Redalyc): 4 reg., linhas 264, 265, 266, 949

**Proposta**: mover para campo dedicado (`id_externo`), tratar
`Numero_DOI` como vazio.

### 2.9. Texto descritivo "Não consta" — **14 registros**

Variantes: `'Não tem'`, `'Não consta'`, `'Não consta informação'`,
`'Não informado'`, `'Essa informação não consta'`, `'Não tem esta
informação.'`. Linhas 583, 600, 791, 807, 818, 819, 825, 865, 878,
886, 891, 897, 899, 900.

**Proposta**: tratar como vazio. Estes textos vieram de um analista
preenchendo a mão em vez de deixar em branco.

### 2.10. Número de ordem do item — **59 registros**

Sequência `'1','1','1','1','2','2','2','2','3','3'…` no campo DOI.
Provavelmente o estudante colou o número da coluna "Item" do tutorial
(item 1) no campo DOI por engano. Linhas: 6–17, e várias outras.

**Proposta**: tratar como vazio. Alertar a equipe (Teresinha, Janja,
Leliana) para reforçar a instrução.

### 2.11. DOI com lixo textual — **6 registros**

| Linha | Valor | Lixo |
|---|---|---|
| 198, 201, 215 | `10.1177/0022022112466592 OnlineFirst Version of Record - Nov 14, 2012` | nota de release |
| 794 | `10.1017/S0267190519000114[Opens in a new window]` | texto de hyperlink |
| 856 | `: 10.7596/taksad.v7i3.1723` | dois-pontos no início |
| 555 | `0.1016/j.pnpbp.2017.12.001` | falta o `1` no `10.` |
| 1253 | `0.1007/s11251-024-09665-9` | falta o `1` no `10.` |

**Proposta**: regex `r'10\.\d{3,9}/[^\s\[\]]+'` extrai o DOI canônico
em todos esses casos (o `0.1` precisa de regra adicional para inserir o
`1`).

### 2.12. ISBN puro (livros, não artigos) — **10 registros**

Valores como `9780128038031`, `9780128093245` (13 dígitos começando
com `978`). Linhas 85–90 e outras. Indica que o registro é um
**capítulo de livro**, não um artigo de periódico.

**Proposta**: mover ISBN para coluna dedicada e marcar
`tipo_publicacao = 'capitulo_livro'`.

### 2.13. ISBN + DOI grudados — **2 registros**

- linhas 135, 136: `ISBN 9780128038031 / https://doi.org/10.1016/B978-0-12-803803-1.00006-9.`

**Proposta**: extrair os dois e separar em colunas.

### 2.14. Número grande com vírgulas-de-milhar (Excel) — **5 registros**

- linha 541: `'1,011,772,051,570,710,000,000'`
- linha 545: `'101,016,201,804,006'`
- linha 546: `'10,100,220,761'`
- linha 549: `'101,186,129,110,180,000'`
- linha 550: `'1,011,772,051,570,710,000,000'`

Excel formatou números grandes com vírgulas-de-milhar e perdeu
precisão. Análogo ao caso 2.3 (notação científica).

**Proposta**: irrecuperável. Refazer manualmente.

### 2.15. Resto inclassificável — **21 registros**

Casos sem padrão recorrente. Mais notáveis:

| Linha | Valor | Diagnóstico |
|---|---|---|
| 184 | `Language Sciences 37 (2013) 122–135` | citação completa |
| 290 | `J. Behav. Ther. & Exp. Psychiat. 43 (2012) 699e704` | citação |
| 234 | `SIMULATION published online 23 May 2011` | nota editorial |
| 1182 | `i s s n 1 6 4 6 ‑ 4 9 9 0` | ISSN com espaços entre dígitos |
| 1210 | `Introdução à seção temática: Entre continuidades…` | **título do artigo no campo DOI** |
| 194 | `{doi:10.1177/1029864916670700` | bibtex truncado |
| 263 | `doi107764` | "doi" + número grudados |
| 541, 550 | `1,011,772,051,570,710,000,000` | número com vírgulas (Excel) |

---

## 3. Duplicatas — 3 categorias

Aplicando as duas chaves (título normalizado e DOI canônico extraído):

### 3.1. Duplicata REAL (mesmo artigo + mesmo analista)

São os candidatos diretos a remoção. **Total: 6 grupos por título, 2
grupos por DOI, totalizando ≤ 16 registros únicos.**

| Linhas | Analista | Título / DOI |
|---|---|---|
| 219, 220 | `Gillian` / `GIllian` (mesma pessoa) | `Cornell Hospitality Quarterly` — DOI 10.1177/1938965511433293 |
| 1178, 1189 | `Yone Carneiro de Santana Gonçalves` | `A gestão educacional…` — DOI 10.22633/rpge.v26i00.16741 |
| 328, 423 | (verificar) | `Tracking students' visual attention on manga-based interactive e-book…` |
| 330, 432 | (verificar) | `Intelligent algorithms of processing of information in the production…` |
| 340, 433 | (verificar) | `For a refoundation of artificial immune system research…` |
| 461, 530 | (verificar) | `The analysis of social resource mobilization on new media…` |

**Proposta**: revisão manual rápida; manter o registro mais completo de
cada par e descartar o(s) outro(s).

### 3.2. Multi-análise legítima (mesmo artigo + analistas distintos)

Esperado pelo tutorial (item 8): cada estudante faz a sua análise.
**57 grupos por título, 23 por DOI**. Não é problema, mas é informação
útil para o curador entender quantas análises por artigo existem.

### 3.3. Suspeita (mesmo artigo + um ou mais registros sem analista)

**256 grupos por título, 190 por DOI.** Padrão recorrente: o artigo
aparece N vezes com analista vazio (provavelmente linhas pré-preenchidas
do catálogo bruto antes de qualquer análise) e às vezes 1-2 vezes com
analista real.

Caso exemplar (DOI `10.22633/rpge.v26i00.16741`, "A gestão educacional
e os referenciais cognitivos…"): aparece **18 vezes**, com 13 sem
analista, 1 com `Professor Doutor Sebastião de Souza Lemes,` (com
vírgula final), e 4 com analistas reais (Yara, Ana Cleide, Yone,
Cândida, Kleber).

**Proposta**: para cada grupo:
1. Manter as linhas com analista preenchido como análises individuais.
2. Decidir destino dos registros sem analista:
   - Se há análises preenchidas para o mesmo artigo → remover os
     registros vazios (eram apenas placeholders).
   - Se nenhum analista preencheu → manter **um único** registro como
     "artigo catalogado mas não analisado".

### 3.4. Conflito entre chaves título e DOI

Em alguns grupos, o título normaliza igual mas o DOI varia (porque o
DOI tá errado ou em formatos diferentes). E vice-versa: mesmo DOI com
títulos transcritos diferentemente. Isto gera **resultados maiores
quando se cruza as duas chaves**:

- Total único de grupos por título OU DOI: ≈ 280+ (não calculado
  exatamente — precisa de pass de união).
- Na importação do legado para o sistema novo: cruzar as duas chaves
  antes de decidir o que é dedup.

---

## 4. Campo `Analista` — variantes de grafia e ruído

- 410 preenchidos / 1.033 vazios (72%).
- 82 chaves únicas (case-insensitive, sem acentos).

### 4.1. Variantes de grafia da mesma pessoa — 10 grupos

| Forma canônica sugerida | Variantes |
|---|---|
| `Alício Rodrigues Matos` (16 reg.) | `Alicio Rodrigues Matos` (4×), `Alício rodrigues Matos` (1×) |
| `Tânia Ferreira dos Santos Bomfim` (15 reg.) | `TANIA FERREIRA DOS SANTOS BOMFIM` (1×) |
| `Regis Glauciane` (15 reg.) | `REGIS GLAUCIANE` (5×) |
| `Francineide Marques` (13 reg.) | `francineide marques` (6×) |
| `Moisés Viana` (7 reg.) | `Moises Viana` (3×) |
| `Gillian` (5 reg.) | `GIllian` (1×) — primeiro nome só |
| `Floriano Barboza` (5 reg.) | `floriano Barboza` (1×) |
| `Francisco Cleiton Alves` (5 reg.) | `Francisco Cleiton alves` (1×) |
| `Regis Glauciane e Fabio Barreto` (3 reg.) | `Regis Glauciane e Fábio Barreto` (1×) |
| `Silvia Karla Almeida dos Santos` (3 reg.) | `SIlvia Karla Almeida dos Santos` (1×), `Silvia Karla ALmeida dos Santos` (1×) |

**Proposta**: forma canônica = Title Case com acentuação da variante
mais frequente. Aplicar via mapa explícito (não regex genérico, para
evitar erros tipo `dos` virando `Dos`).

### 4.2. Ambiguidades não-detectáveis automaticamente

Estes casos a chave normalizada **não** funde, mas provavelmente são a
mesma pessoa:

| Variante A | Variante B | Linhas |
|---|---|---|
| `Vera Ferreira Andrade de Almeida` (3 reg.) | `Vera Ferreira Almeida de Andrade` (1 reg.) | 1393, 1394, 1414, 1415 |
| `Regis Glauciane` (15 reg.) | `REGIS GLAUCIANE SOUZA` (7 reg.) | múltiplas |

**Proposta**: revisão manual pela equipe — só os co-orientadores
sabem confirmar se são a mesma pessoa.

### 4.3. Texto inválido no campo Analista

| Linha | Conteúdo (truncado) |
|---|---|
| 908 | `Importancia de um estudo analitico sobre os conhecimentos didático-matematico…` (título do artigo) |
| 1187 | `O termo Dêitico e sua abordagem na perspectiva linguística…` (resumo da análise) |
| 1188 | `Os autores fazem uma análise cognitiva da atuação transitória…` (resumo da análise) |

**Proposta**: as linhas 908, 1187, 1188 têm dados embaralhados. O
analista provavelmente preencheu campos errados. Recuperar manualmente
verificando o restante do registro.

### 4.4. Apenas o primeiro nome — 5 grupos / 20 registros

`Adilson` (1×), `AMANAIARA` (5×), `Gillian` (5×), `Leidiane` (4×),
`Robenilson` (5×).

**Proposta**: pedir aos coordenadores para identificarem nome completo.

### 4.5. Co-autoria no mesmo campo

`Regis Glauciane e Fabio Barreto` (3 reg.). Mas existem também
`Regis Glauciane` (15×) e `Fabio Barreto` (10×) separados.

**Proposta**: confirmar com a equipe se é uma análise dupla (manter
como tal) ou se foram duplicatas dos individuais (descartar).

### 4.6. Vírgulas e títulos acadêmicos

- `Professor Doutor Sebastião de Souza Lemes,` (1×) — vírgula final
  artefato.
- `Igor  Žunkovič,` (1×) — vírgula final + espaço duplo.

**Proposta**: strip de vírgulas/pontos finais; remover título
acadêmico (ou padronizar em campo separado).

---

## 5. Outros campos

### 5.1. `Ano` — 4 valores fora da janela

| Linha | Valor | Provável |
|---|---|---|
| 716 | `218` | dígito faltando — `2018`? |
| 922 | `21` | `2021`? |
| 914, 1156 | `2921` | dedo errado — `2021`? |

### 5.2. `Pagina_Inicial` / `Pagina_Final`

- 227 registros com ambas vazias (esperado para muitos artigos online).
- **3 com `pf < pi`** (provável troca de campos):
  - linha 191: pi=210, pf=202
  - linha 288: pi=3071, pf=3070
  - linha 905: pi=742, pf=63

### 5.3. `Presenca_AC_*` — 5 campos com 8+ variantes não-booleanas

Cada um dos 5 campos tem mistura de:
- ~70% vazios
- `Sim`/`Não` em variações de capitalização
- `S`/`N`/`0`/`1`/`x`
- **Texto livre** que não é booleano: descrição da metodologia, parte
  do resumo, lista de referências (ex: linha 215 em
  `Presenca_AC_no_Resumo`: `'10.1177/1088868312467086 OnlineFirst…'`).

**Proposta**: separar booleano de texto. Quando o conteúdo é texto
livre, deixar `Presenca_AC_* = null` e mover o texto para
`Outras_Observacoes` ou similar.

### 5.4. `Pertinencia_para_Area`

- 1.116 vazios.
- 22 registros com texto longo (>30 chars) onde deveria estar Sim/Não.
- Variantes de capitalização: `Sim`/`sim`/`SIM`/`S`, `Não`/`não`/`NÃO`/`N`/`n`.

### 5.5. `Define_Conceito`

- 1.201 vazios.
- 34 registros com texto longo (>100 chars) — provavelmente a definição
  copiada literalmente, conforme orienta o tutorial item 6.3.
- Mas há também valores curtos como `'Contribui'` e `'Contexto atual'`
  que parecem ruído.

### 5.6. `Base_de_Consulta` — variantes de capitalização

| Forma | Reg. |
|---|---:|
| `Web of Science` | 572 |
| `Redalyc` | 254 |
| `Scopus` | 236 + `SCOPUS` 1 + `scopus` 1 |
| `Science Direct` | 217 + `SCience Direct` 1 |
| `Sage` 54 + `SAGE` 16 | 70 |
| `Repositório UFBA` | 21 |
| `ELSEVIER` | 1 (provavelmente Science Direct) |
| (vazio) | 69 |

**Proposta**: padronizar via mapa de canônicos (já existe em
`apps/vocabulario/fixtures/`).

### 5.7. `Outra_Base_de_Consulta`

- 1.310 vazios (91%).
- Variantes Scielo: `Scielo` (11×), `SciELO` (8×), `SCIELO` (4×).
- 51× `Não`, 5× `-`, 4× `Não se aplica` — todas significam "vazio".

### 5.8. `Resumo`

- 62 vazios.
- 24 suspeitamente curtos (<100 chars), incluindo:
  - linha 84: `'Os autores não apresentaram um resumo'`
  - linha 210: `'SEM RESUMO'`
  - linha 256: `'Não há!'`
  - linha 269, 270, 272: `'Resumen: Portugués Inglés Texto completo:…'` (cabeçalho
    do site copiado em vez do resumo)
- **217 grupos de resumos idênticos abrangendo 603 registros**. Causas:
  - copy-paste do mesmo resumo para múltiplas análises do mesmo artigo
    (legítimo se é mesmo o mesmo artigo);
  - **copy-paste cruzado**: o estudante colou o resumo de outro
    artigo. Cruzar com chave de DOI/título resolve.

**Proposta**: para cada grupo de resumos idênticos onde título e DOI
não batem, sinalizar como suspeita de copy-paste cruzado.

### 5.9. `Titulo_do_artigo`

- 13 vazios.
- 149 em CAIXA ALTA TODA — ruído visual no front-end. Os mais
  problemáticos são os títulos copiados de catálogos.
- 4 com possível mojibake — falsos positivos (na verdade são UTF-8 ok).

**Proposta**: aplicar Title Case a títulos em caixa alta na
apresentação (não destruir o dado original).

### 5.10. `Palavras_Chaves`

- 131 sem palavras-chave.
- Separadores heterogêneos:
  - `;` em 628 registros
  - `,` em 381 registros
  - `\n` em 187 registros
  - `/` em 16, ` - ` em 11, `|` em 1

**Proposta**: na hora da migração, splittar em qualquer um dos
separadores e canonizar como lista. (Estratégia já presumida.)

### 5.11. `Link_de_Acesso`

- 1.062 vazios (74%).
- 33 com formato inválido (não começa com `http(s)://`):
  - linha 150: `'Language & Communication'` (nome do periódico)
  - linha 159: aspas extras grudadas
  - linha 228: `'TTP://…'` (faltou o `H`)
  - linha 362, 377: `file:///C:/Users/…` (caminho local)
  - linhas 306, 315, 385, 386, 396…: DOI no campo de link
- **8 grupos de URLs duplicadas** abrangendo 22 registros. Pode
  indicar: (a) duplicata real do artigo; (b) link genérico do
  periódico em vez do link do artigo.

### 5.12. `Universidade` vs `Vinculacao_Institucional`

- `Vinculacao_Institucional` vazia: 227 (campo do **artigo**).
- `Universidade` vazia: 1.180 (campo do **analista**, não do artigo).
- Ambas vazias: 213.

Conforme `analise_legado.md` §9, `Universidade` é o campo do quem
cadastrou e tem baixa qualidade — só interessa para preservar histórico.

### 5.13. `Outras_Observacoes`

- 1.282 vazios (89%).
- 54× `'Enviado por Josualdo Dias'` — único padrão recorrente.
  Provavelmente um curador adicionou esse marcador.
- 51× `'Não'` — significam vazio (deveria ser branco).

### 5.14. `Artigo_Pago`

- 1.154 vazios.
- 217 `não`, 51 `sim`, 16 `n`, 2 `s`, 1 `nao`.
- 1 `não identificado no texto`, 1 `referência` (texto livre suspeito).

---

## 6. Encoding e sujeira textual

### 6.1. Mojibake clássico (`Ã£`/`Ã©`/etc.) — **não detectado** ✅

O JSON está em UTF-8 limpo. Boa notícia.

### 6.2. Caracteres invisíveis — 43 registros

NBSP (`\xa0`), ZWSP (`​`), BOM (`﻿`) em campos de texto.
Exemplos:
- linha 65 (`Nomes`): `'Jansen, Willemijn J ; Ossenkoppele, Rik ; …'`
  (semi-colons cercados por NBSP).
- linha 174 (`Titulo_do_artigo`): `'…biochemical road map'` com NBSP
  entre `road` e `map` + tabs ao final.
- linha 100 (`Resultados`): texto com 2 ZWSP no meio.

**Proposta**: substituir NBSP/ZWSP por espaço ASCII normal antes da
indexação. Não afeta a leitura humana, mas atrapalha busca.

### 6.3. Tabs no meio de texto — 95 registros

Causa: os campos longos do Sheets foram exportados com tabs internos
(provavelmente o estudante colou texto que tinha tabulações). Exemplo:
linha 3 `Resumo` tem 4 tabs no meio.

**Proposta**: substituir por espaço único na hora da migração.

### 6.4. Espaços duplicados — 262 registros

Inúmeros campos textuais com `'  '` interno. Cosmético; corrigível
via `re.sub(r'\s+', ' ', v)`.

### 6.5. Hífen não-padrão (`‑` U+2011, `­` U+00AD) — 2 registros

Linhas 980, 1182. Cosmético.

---

## 7. Recomendações de correção priorizadas

| # | Ação | Reg. | Esforço | Automatizável? |
|---|---|---:|---|---|
| 1 | Definir critério de dedup do legado (título OU DOI) antes da importação | — | baixo | (decisão de produto) |
| 2 | Extrair `10.x/y` de URLs `https://doi.org/...` | 200 | trivial | sim, regex |
| 3 | Stripar prefixo `DOI:` / `DOI ` / `: ` / `1234 DOI` | 60 | trivial | sim, regex |
| 4 | Strip de citações do tipo `[Opens in...]`, `OnlineFirst...` | 6 | trivial | sim, regex |
| 5 | Padronizar variantes de grafia em `Analista` (10 grupos) | ~30 | baixo | sim, mapa |
| 6 | Padronizar `Base_de_Consulta` (Sage/SAGE, etc.) | ~20 | trivial | sim, mapa |
| 7 | Limpar tabs/NBSP/espaços duplicados em texto | ~400 | trivial | sim |
| 8 | Tratar 14 "Não consta", 59 "número de ordem" como vazio em DOI | 73 | trivial | sim |
| 9 | Resolver duplicatas REAIS (mesmo artigo + mesmo analista) | 12 | médio | manual |
| 10 | Reverter ISBN em notação científica (`9.78E+12`) | 48 | **alto** | **manual** — perda de precisão |
| 11 | Mover ISSN no campo DOI para coluna `ISSN` | 84 | médio | parcial |
| 12 | Recuperar DOIs com `/` apagada (`'101016'` etc.) | 158 | **alto** | manual via Crossref |
| 13 | Decidir destino dos 256 grupos suspeitos (mesmo artigo + analista vazio) | ~600 | **alto** | manual |
| 14 | Investigar 217 grupos de resumos idênticos para detectar copy-paste cruzado | 603 | médio | semi-auto |
| 15 | Corrigir 4 anos fora da janela | 4 | trivial | manual |
| 16 | Corrigir 3 páginas invertidas | 3 | trivial | manual |
| 17 | Recuperar conteúdo das linhas 908, 1187, 1188 (campos embaralhados) | 3 | médio | manual |

---

## 8. Escopo da auditoria e o que o sistema novo já resolve

Esta auditoria cobre **apenas o que já foi lançado** (1.443 registros
do dump do Google Forms). A próxima rodada de catalogação acontecerá
no sistema AnCo em desenvolvimento, com fluxo diferente:

> O analista digita o identificador do artigo (DOI/ISBN); o sistema
> busca metadados no Crossref e preenche automaticamente título,
> autores, periódico, ano, páginas, etc. O analista preenche apenas os
> campos de análise (presença do termo, pertinência, definição,
> objeto, objetivo, …) num formulário web com boa UX, salvo direto no
> backend.

Isso quer dizer que **a maior parte dos problemas catalogados aqui não
voltará a acontecer** — eles são artefatos da combinação Google Forms
+ Sheets + texto livre. Para registro:

| Problema do legado | Por que não volta no sistema novo |
|---|---|
| DOI com `/` apagada, ISBN em notação científica, número grande com vírgulas | DOI/ISBN trafega como string no DRF/PostgreSQL; nunca passa por planilha |
| ISSN ou URL no campo DOI | Sistema valida o identificador antes de aceitar e busca no Crossref — ISSN/URL falha na validação |
| `'1','2','3'` (número de ordem) no campo DOI | Idem — não bate com regex de DOI |
| "Não consta", "Não tem" em DOI | Campo opcional com botão "sem DOI"; texto livre não é aceito |
| Variantes Scopus/SCOPUS/scopus, Sage/SAGE | Vocabulário controlado em FK (`apps/vocabulario`), não campo livre |
| Variantes de grafia em Analista (Alício/Alicio) | `Analise.analista` é FK para `User`; cada pessoa é uma só |
| Texto livre em `Presenca_AC_*` | Campo booleano no modelo (true/false/null) |
| Resumos idênticos entre artigos | Resumo vive em `Artigo`, não em `Analise` — não é re-digitado por análise |
| Multi-análise legítima (mesmo artigo, vários analistas) | Modelo já prevê: `Analise` tem FK para `Artigo`, M2M de revisores |
| Mojibake / NBSP / tabs / encoding | UTF-8 garantido pelo Postgres + Django |

### 8.1. O que fica como dívida desta auditoria para a Fase 1

Itens que precisam de decisão **na importação do legado** (não da
nova rodada):

1. **48 ISBNs em notação científica** e **5 números com vírgulas-de-
   milhar** → precisão perdida; vão entrar como `legacy:HASH` ou
   exigem busca manual no Crossref a partir do título.
2. **158 DOIs com `/` apagada** → tentar reconstruir via Crossref API
   (busca por título + ano + periódico) durante a migração; o que não
   bater vira `legacy:HASH`.
3. **256 grupos suspeitos** (mesmo título + analista vazio) → o
   migrador da Fase 1 já trata via `update_or_create` com chave
   `(artigo, analista)`. Os registros sem analista convergem para o
   `User legado-anonimo` único, então deduplicam naturalmente.
4. **6 grupos de duplicata real** → precisam decisão manual antes da
   importação: qual versão preservar.
5. **3 linhas com campos embaralhados** (908, 1187, 1188) → revisão
   manual antes de importar.
6. **10 grupos com variantes de grafia em Analista** + **2 casos não
   detectáveis** (`Vera A. de B.` vs `Vera B. de A.`, `Regis Glauciane`
   vs `REGIS GLAUCIANE SOUZA`) → mapa explícito de fusão de usuários
   antes ou depois da importação. Curador funde manualmente o que o
   automatizado não pegar.

### 8.2. Itens que o sistema novo cobre por design — confirmar na Fase 5/6

Para checar se o sistema realmente protege contra estes problemas,
quando chegar a fase de cadastro pelo analista:

- [ ] Validação do identificador no submit (regex de DOI ou consulta
      ao Crossref retornando 200) antes de aceitar o registro.
- [ ] Vocabulários controlados (`base`, `area`, `epistemologia`,
      `teoria`) com sinônimos resolvendo variantes.
- [ ] `Analise.analista` como FK obrigatória — sem campo livre.
- [ ] Campos de presença AC e pertinência como `BooleanField(null=True)`
      no modelo, renderizados como radio Sim/Não/Indefinido.
- [ ] UI permite apontar um artigo já catalogado em vez de re-digitar
      metadados (resolve resumos idênticos por copy-paste).

---

*Auditoria gerada a partir do JSON original (1.443 registros) sem
alterá-lo. As correções automatizáveis (§7 itens 2–8) já estão na
estratégia do migrador da Fase 1 — ver `docs/migracao/analise_legado.md`
§10. Os itens manuais (§8.1) precisam de decisão antes da importação.*
