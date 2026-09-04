# Problemas a considerar — `base-anco-revisada.xlsx`

**Arquivo de entrada**: `/home/anco-paulovicente/base-anco-revisada.xlsx` (286 KB)
**JSON gerado**: `/home/anco-paulovicente/base-anco-revisada.json` (1.2 MB, 653 registros)
**Conversor**: `tools/converter_base_revisada.py`
**Análise**: 2026-05-27

Este documento lista os problemas detectados na base revisada antes da
importação. Estilo e objetivo equivalentes a `analise_legado.md`: rodar
análise exploratória **antes** de importar para que o migrador trabalhe
com base em estatísticas reais.

---

## 1. Sumário numérico

| Métrica | Valor |
|---|---|
| Registros úteis | 653 (linhas 3–655 do xlsx; linha 1 = botão "VOLTAR", linha 2 = cabeçalho) |
| Colunas nomeadas | 26 (A–Z); colunas AA–AM existem mas estão vazias |
| Range de anos | 2001–2023 (sem nulos) |
| Sobreposição com legado (`base-referencial-corrigida.json`) | **523 de 650 títulos = 80,5%** |
| Registros novos (não presentes no legado) | **127** |

---

## 2. Problemas estruturais (a corrigir antes ou durante o migrador)

### 2.1. Cabeçalho inflado por colunas vazias

A linha 1 do xlsx contém apenas a string `"VOLTAR"` em A1 (botão de navegação).
A linha 2 é o cabeçalho real. O conversor pula as duas; quem abrir o xlsx
direto precisa ignorar manualmente.

### 2.2. Colunas deslocadas — 18 linhas corrigidas via heurística

Em 18 linhas, o **link de acesso** foi digitado na coluna X
(Universidade), e os campos seguintes (Y "Artigo Pago", Z "Outra Base")
deslocaram-se 1 posição à direita. O conversor detecta pelo formato do
valor em X (`http://`, `file:///`, `[Acesso via …]`, `www.`) e desfaz o
shift. **Linhas afetadas (xlsx)**:

```
119, 142, 166, 285, 318, 321, 324, 334, 401,
429, 494, 501, 521, 545, 547, 550, 562, 577
```

Cada uma fica marcada no JSON com `_origem.alinhamento_corrigido: true`.

### 2.3. Linha 616 — deslocamento grave, **não corrigida automaticamente**

Caso isolado: a partir da coluna P (Objeto), os campos descritivos
recebem `"Sim"` e `"Não"`, e o conteúdo real está espalhado para frente
(Metodologia → "Usabilidade de fones…" deveria ser Objeto; SHERPA em X
parece ser metodologia, etc.). A heurística atual não tem como
reconstruir o alinhamento — campo `_origem.alertas` sinaliza para
revisão manual.

**Ação recomendada**: corrigir L616 no xlsx, regerar o JSON.

---

## 3. Cobertura do modelo de dados

### 3.1. Campos do `Artigo` AUSENTES na base revisada

| Campo do modelo | Disponível no legado? | Disponível na revisada? |
|---|---|---|
| `doi` | sim (585 canônicos) | **não** |
| `isbn` | parcial | não |
| `resumo` | sim | **não** |
| `volume`, `numero`, `pagina_inicial`, `pagina_final` | sim | não |
| `tipo_publicacao` | inferido | não |
| `link_acesso_alternativo` | parcial | não |
| `acesso_aberto` | derivado | não |

**Impacto crítico**:

- **Sem DOI** → impossível deduplicar artigos da revisada com os já
  importados do legado pelo identificador canônico. O matching terá que
  ser por hash determinístico de `título|ano|periódico` (mesma regra do
  `_gerar_identificador_interno` no [apps/acervo/models.py:21-28](apps/acervo/models.py#L21-L28)).
- **Sem resumo** → a busca semântica (Fase 8) perde uma fonte central
  de sinal para os 127 registros novos. Embedding de artigo fica
  baseado só em título + palavras-chave.
- **Sem volume/número/páginas** → citações ABNT/APA geradas pelo
  acervo público ficarão incompletas para esses registros.

### 3.2. Campos da `Analise` AUSENTES

`aspectos_relevantes`, `definicao_extraida`, `referenciais`,
`contexto_producao`, `observacoes`, `resenha_critica` — todos ficam
vazios. Análises importadas vão direto com status `legado` e sem
resenha crítica (consistente com o status: legado é pré-validado, não
exige resenha).

### 3.3. Campos da revisada NÃO mapeáveis em campos do modelo

- **`Título Traduzido (ChatGPT/Gemini)`** (col B) — guardado em
  `_extras.titulo_traduzido`. Decidir: criar novo campo no `Artigo`
  ou descartar.
- **`Outra Base de Consulta`** (col Z) — guardado em
  `_extras.outra_base_consulta`. Aparece em 72 registros (de 653).
  Provavelmente bandeira de "também encontrado em" — descartável se
  não houver caso de uso.

---

## 4. Qualidade dos dados — valores categóricos

### 4.1. Base de consulta — capitalização duplicada

Detectado e já normalizado pelo conversor: `SAGE` (10) → `Sage` (31).
Após normalização: 6 valores únicos (Web of Science, Scopus, Science
Direct, Redalyc, Sage, Repositório UFBA).

### 4.2. Vocabulário `Teoria` — 296 valores únicos, 47% vazio

| Categoria | Contagem |
|---|---|
| `(Não Especificada)` | 306 (~47%) |
| Termos distintos | 296 |
| Variantes de capitalização/pontuação detectadas | 5 grupos (subestimado) |

Exemplos de variantes do mesmo conceito:

- `Linguística Cognitiva` (1) vs `Linguística Cognitiva.` (3)
- `Teoria da Metáfora Conceitual (CMT)` (5) vs `… (CMT).` (1)
- `Abordagem Onto-Semiótica` (4) vs `Abordagem Ontossemiótica` (3) vs `Enfoque Ontosemiótico.` (2)
- `Metáfora Conceitual` (3) vs `Metáfora Conceitual.` (1)

**Ação recomendada**: passo de normalização **antes** de criar
`TermoVocabulario`: lowercase para comparação, strip de ponto final,
mapeamento manual para grafias variantes (Onto-Semiótica/Ontossemiótica/etc).

### 4.3. Vocabulário `Epistemologia` — 171 valores únicos

Top 5 cobre 274 registros (42%): Aplicada/Descritiva (112),
Empírica/Quantitativa (63), Aplicada/Modelagem (42),
Empírica/Experimental (31), Teórica/Conceitual (26).

**Cauda longa**: 156 valores com 1–8 ocorrências cada. Vale revisar se
há variantes (não inspecionei a fundo aqui) e definir taxonomia
controlada para a importação.

### 4.4. Área do conhecimento — 47 valores, sem taxonomia

Coexistem `Psicologia`, `Psicologia da Educação`, `Psicologia Social`,
`Psicologia e Educação`, `Educação`, `Educação/Política Pública`,
`Educação/Linguística`. Não há hierarquia controlada.

**Ação recomendada**: decidir se o `Artigo.area` permanece como string
livre (estado atual) ou vira FK para um vocabulário `Area do
conhecimento`. Se a segunda, definir o mapa.

### 4.5. Periódico — 24 grupos com variantes de capitalização

Mesma revista entrando duas vezes:

| Variante 1 | Variante 2 |
|---|---|
| `NAUCHNYI DIALOG` (6) | `Nauchnyi Dialog` (6) |
| `REVISTA DE ADMINISTRAÇÃO PÚBLICA` | `Revista de Administração Pública` |
| `SOTSIOLOGICHESKIE ISSLEDOVANIYA` | `Sotsiologicheskie Issledovaniya` |
| `UNICIENCIA` | `Uniciencia` |
| … (mais 20 grupos) | |

**Ação recomendada**: normalizar para Title Case ao importar, ou
manter exata mas exibir normalizada. Se manter, periódicos duplicarão
na visão facetada.

### 4.6. Universidade — 507 únicos, sentinelas com gênero variável

`(Não Fornecida)` aparece 99 vezes e `(Não Fornecido)` 11 vezes —
mesma intenção, gêneros diferentes. Conversor preservou ambas como
string (decisão do usuário). 37 registros têm múltiplas instituições
separadas por `;` ou ` and `.

---

## 5. Sentinelas — 17 variantes distintas em uso

Decisão: preservar como string (não converter para `null`). Tabela completa
do que aparece nos dados:

| Sentinela | Ocorrências |
|---|---|
| `(Não Fornecido)` | 494 |
| `(Não Fornecida)` | 99 |
| `(Não Fornecidas)` | 34 |
| `(Não se aplica)` | 8 |
| `(Não consta)` | 5 |
| `(Não Especificado)` | 3 |
| `(Não consta o objetivo no resumo).` | 2 |
| `(Não especificado)` | 2 |
| `(Não consta o objeto no resumo).` | 1 |
| `(Não consta o resultado no resumo).` | 1 |
| `(Não detalhada no resumo).` | 1 |
| `(Não consta no texto fornecido).` | 1 |
| `(Não Tem afiliação)` | 1 |
| `(Não consta informação)` | 1 |
| `(Não Fornecidos)` | 1 |
| `(Não consta o termo AC, …)` | 1 |
| `(Não se aplica, falta o termo AC …)` | 1 |

Também o caractere `-` aparece como sentinela em vários campos
(notavelmente 581 vezes em "Outra Base de Consulta").

**Ação recomendada**: na importação, qualquer string que **começa com**
`(Não` (case-insensitive) é tratada como vazia. O texto literal pode
ser preservado em `Analise.observacoes` se for um sentinela
"explicado" (`… porque …`).

---

## 6. Sentinelas por campo (cobertura efetiva)

Percentual de registros em que o campo é sentinela ou vazio:

| Campo | Cobertura efetiva |
|---|---|
| `artigo.titulo_periodico` | 99.4% (4 sentinelas) |
| `artigo.area` | 100% |
| `artigo.autores` | 99.8% (1 sentinela) |
| `artigo.palavras_chaves` | 89.1% (71 sentinelas) |
| `artigo.vinculacao_institucional` | 82.8% (112 sentinelas) |
| `artigo.link_acesso` | **27.4%** (474 sentinelas — 72,6% sem link real) |
| `analise.objeto` | 99.7% |
| `analise.objetivo` | 99.2% |
| `analise.foco` | 99.8% |
| `analise.metodologia` | 99.2% |
| `analise.resultados` | 98.6% |

### 6.1. Link de acesso — tipologia

| Tipo | Contagem | % |
|---|---|---|
| Sentinela `(Não …)` | 474 | 72.6% |
| `http(s)://…` | 108 | 16.5% |
| `[Acesso via SAGE / DOI …]` | 59 | 9.0% |
| `file:///` (local) | 4 | 0.6% |
| Outro | 8 | 1.2% |

Apenas **108 links são URLs públicas reais**. Os 59 com prefixo
`[Acesso via …]` carregam o DOI dentro do texto — pode ser
parseado para recuperar o DOI canônico (recuperando parcialmente o
campo ausente).

### 6.2. Link inválido isolado

`L432`: `https://portalseer.ufba.br/index.php/revistaici/article/view/3214/2340 (pt-BR)`
— sufixo ` (pt-BR)` quebra o `URLField`. Stripar tudo após o primeiro
espaço antes de salvar.

---

## 7. Duplicatas

### 7.1. Internas (na própria revisada)

2 grupos detectados por chave `(título, ano, periódico)`:

- 2× `'A gestão educacional e os referenciais cognitivos e normativos…'` (2022)
- 2× `'Художественное воплощение русского национально-культурного…'` (2019)

Total: 4 registros duplicados.

### 7.2. Cruzamento com legado

523 títulos da revisada (80,5%) já existem no legado por match exato de
título normalizado. Decisão a tomar antes da importação:

- **Sobrescrever** análises legadas com as revisadas (a revisão é
  considerada autoritativa)?
- **Coexistir** como segunda análise sobre o mesmo artigo (modelo
  permite, dado `UniqueConstraint(artigo, analista)` mas exige
  analista diferente)?
- **Ignorar** os 523 e importar apenas os 127 novos?

**Recomendação**: clarificar com o autor da revisão. A escolha
afeta o `management command` de importação.

---

## 8. Recomendações por prioridade

### Alta — bloqueia importação consistente

1. Corrigir manualmente **L616** no xlsx.
2. Decidir política de **sobreposição com legado** (item 7.2).
3. Decidir destino dos campos extras (`titulo_traduzido`,
   `outra_base_consulta`): novo campo no `Artigo` ou descarte.
4. Extrair **DOI dos 59 links `[Acesso via …]`** via regex
   (`DOI 10\.\d+/\S+`) para preencher parcialmente o gap do campo DOI.

### Média — qualidade do acervo

5. Mapa de **normalização de teorias** (variantes de capitalização e
   pontuação) antes de criar `TermoVocabulario`.
6. **Title-case nos periódicos** com 24 grupos duplicados.
7. **Sentinelas → vazio** na importação (regex `^\(Não`), preservando
   o texto explicativo em `observacoes` quando houver substância.
8. **L432**: limpar sufixo ` (pt-BR)` do link.

### Baixa — pode ficar para depois

9. Decidir taxonomia da `area` (string livre vs vocabulário
   controlado).
10. Revisar a cauda longa de `Epistemologia` (156 valores únicos com 1–8
    ocorrências) para detectar mais variantes.

---

## 9. Próximos passos sugeridos

1. Levar este relatório ao autor da curadoria para decisões dos itens
   1–4 acima.
2. Estender o conversor com:
   - Extração de DOI de `[Acesso via …]`.
   - Mapa de normalização de teorias.
   - Limpeza do link da L432.
3. Escrever `apps/acervo/management/commands/migrate_base_revisada.py`
   seguindo o padrão idempotente do `migrate_legacy` (CLAUDE.md §9.1).
4. Rodar `--dry-run` e revisar log antes da importação real.
