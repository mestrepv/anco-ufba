# Análise exploratória da base legada

**Arquivo**: `dados/legado/base-referencial-original.json`
**Geração**: 2026-04-29 (Fase 1)
**Origem**: dump do Google Forms + Sheets que vinha alimentando o catálogo
desde 2018 (estimativa).

Este documento atende ao requisito do CLAUDE.md §9.1: rodar análise
exploratória **antes** de importar, para que o migrador seja escrito com base
em estatísticas reais e não em suposições da especificação.

---

## 1. Sumário numérico

| Métrica | Valor |
|---|---|
| Total de registros | **1.443** |
| Campos por registro | 40 |
| Range de anos válidos | 1999–2024 |

## 2. Campo `Ano`

| Categoria | Contagem |
|---|---|
| Inteiro válido (`1900 ≤ ano ≤ 2026`) | 1.409 |
| Inteiro inválido | 4 (valores: `21`, `218`, `2921`) |
| Vazio (`''`/null) | 30 |

**Estratégia do migrador**: inteiros fora da janela viram `null` com log de
aviso; vazios também viram `null` silenciosamente.

## 3. Campo `Numero_DOI`

Formatos detectados em 1.443 registros (categorias se sobrepõem em alguns
casos):

| Categoria | Contagem |
|---|---|
| Vazio (`''`/`-`) | 121 |
| Prefixo `DOI: ` antes do valor | 47 |
| Formato canônico `10.xxxx/yyy` | 585 |
| ISSN no campo (ex: `0138-9130`) | 23 |
| URL ou contém `doi.org` | 234 |
| Outros formatos | restante |

**Estratégia**:
- Stripar prefixo `DOI:` (case-insensitive).
- Para URLs `https://doi.org/10.xxxx/...`, extrair a parte canônica.
- Para ISSN no campo DOI, **não** usar como DOI (ISSN identifica o
  periódico, não o artigo) → tratar como "sem DOI".
- Sem DOI utilizável → gerar **identificador interno determinístico** com
  prefixo `legacy:` seguido de hash SHA1 truncado a 16 chars de
  `título|ano|periódico`. Garante idempotência (mesma entrada → mesmo ID).

## 4. Campo `Link_de_Acesso`

| Categoria | Contagem |
|---|---|
| Vazio (`''`/`-`) | **1.062** (~74%) |
| Preenchido | 381 |

**Estratégia**: registros sem link entram com `link_acesso=''` e
`eh_legado=True`. Front-end (Fase 5) exibirá selo "Acervo histórico — link
não disponível" conforme §8.1 da especificação.

## 5. Campo `Analista`

| Categoria | Contagem |
|---|---|
| Vazio | **1.033** (~72%) |
| Preenchido (94 nomes únicos) | 410 |

Nomes únicos têm variantes massivas de capitalização (`GENIVALDO FERREIRA SÁ`
vs `Genivaldo Ferreira Sá`, `francineide marques` vs `Francineide Marques`).

**Estratégia**:
- Para registros com analista preenchido: criar `User` com `eh_legado=True`,
  papel `leitor`, e-mail placeholder `legado-<slug>@anco.local` (sem senha
  utilizável). Username = slug do nome.
- **Normalização de variantes**: usar Title Case do nome trimado como chave
  de deduplicação. Variantes de mesma pessoa convergem para um único `User`.
  Curador pode fundir/separar depois.
- Para registros sem analista: vincular a um `User` único `legado-anonimo`
  criado pelo próprio migrador. Mantém o registro citável sem inflar a
  base de usuários.

## 6. Campos de presença (`Presenca_AC_*`)

5 campos com **8+ variantes** cada: `''`, `'Sim'`, `'Não'`, `'sim'`, `'não'`,
`'NÃO'`, `'SIM'`, `'S'`, `'N'`, `'1'`, `'0'`, `'x'`, `'nao'`.

**Estratégia** — função `_para_booleano(valor)`:
- True: `sim`, `s`, `1`, `x`, `yes`, `y` (case-insensitive)
- False: `não`, `nao`, `n`, `0`, `no` (case-insensitive)
- Outros (texto livre, vazio): `null`

Campo `Pertinencia_para_Area`, `Aspectos_Relevantes` e `Define_Conceito`
têm conteúdo misto (booleano + texto descritivo). Quando o conteúdo é
texto longo (>3 chars e fora do mapeamento), o booleano fica `null` e o
texto é preservado em `aspectos_relevantes` (TextField) ou
`definicao_extraida` (TextField), conforme o caso.

## 7. Bases de consulta

12 valores distintos no campo, mas com variantes case-sensitive
(`Scopus`/`SCOPUS`/`scopus`, `Sage`/`SAGE`):

| Base | Registros |
|---|---|
| Web of Science | 572 |
| Redalyc | 254 |
| Scopus | 236 |
| Science Direct | 217 |
| (vazio) | 69 |
| Sage | 54 |
| Repositório UFBA | 21 |
| SAGE (variante) | 16 |
| outros | resto |

**Estratégia**: vocabulário `base` da fixture inicial cobre todas com
sinônimos para deduplicação. `TermoVocabulario.buscar_canonico` resolve
a variante.

## 8. Epistemologia e Teoria

| Métrica | Epistemologia | Teoria |
|---|---|---|
| Vazio | 1.257 (~87%) | 1.261 (~87%) |
| Preenchido | 186 | 182 |

A maioria dos preenchidos é **texto livre não-canônico** (frases longas
descritivas), não um termo de vocabulário. Variantes claras existem para
"Empirismo" (5 grafias diferentes) e "Cognição".

**Estratégia**:
- Variantes mapeáveis (sinônimos da fixture) → vinculam ao termo canônico.
- Texto livre não-mapeável → cria `TermoVocabulario` com `ativo=False`,
  nome truncado a 200 chars. Curador depois funde, desabilita ou promove.
- Vazios → não vincula nada (M2M permite zero termos).

## 9. Outros campos sem dados confiáveis

- `Timestamp_Envio`: presente mas mostly vazio. Ignorado pelo migrador.
- `Universidade`: campo da pessoa que cadastrou (não do artigo). Ignorado
  pelo migrador — `vinculacao_institucional` do `Artigo` vem de
  `Vinculacao_Institucional` (do artigo, não do analista).
- `Outra_Base_de_Consulta`: anexado em `observacoes` da Análise se
  preenchido, com prefixo "Outra base: ".
- `Termos_mais_frequentes`: anexado em `observacoes` quando útil.

## 10. Idempotência

O migrador usa `update_or_create` com chave determinística:

- `Artigo`: chave `doi` (canônico ou `legacy:HASH`).
- `User legado`: chave `username` (slug do nome ou `legado-anonimo`).
- `Analise`: chave `(artigo, analista)` — combinação única já constraint
  no modelo.

Rodar duas vezes não duplica. Rodar com dados modificados atualiza in-place.
Logs em INFO indicam o que foi normalizado em cada registro.
