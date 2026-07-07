# Facetação do vocabulário Epistemologia — alinhamento a Fróes Burnham

> **Status:** aplicado em produção (reversível). Para apreciação das
> coordenadoras (Profa. Terezinha Fróes / Profa. Leliana). Se não for aprovado,
> desfaz-se com um comando (ver §5). Complementa
> `docs/proposta-evolucao-matriz-froes.md`.

## 1. Motivação

O campo **Epistemologia** foi gerado dos valores livres do acervo legado
(Google Forms) e virou um "balaio": 106 termos ativos misturando **quatro
categorias distintas** — postura epistemológica, método, disciplina e domínio de
aplicação. Isso contraria a distinção que a própria Fróes (com Lage e Michinel,
em *Abordagens epistemológicas da cognição*) faz entre **epistemologia** e as
demais dimensões, e impede **ler a postura epistemológica do acervo** — que é o
que a Análise Cognitiva quer tornar visível.

**Princípio:** organizar **sem apagar** e **respeitando as formas como aparecem
na literatura** (multirreferencialidade não purifica; dá estrutura à
pluralidade). Nenhuma análise é alterada; o acervo legado fica intocado.

## 2. O que foi feito (aditivo e reversível)

- Novo campo **`grupo`** em `TermoVocabulario` (migration `vocabulario 0004`),
  com as facetas: `paradigma`, `metodologia`, `disciplina`, `aplicacao`, `lixo`.
- Comando `facetar_epistemologia` classificou os termos por heurística de
  palavras-chave + correções pontuais (`_OVERRIDES`).
- O **picker de Epistemologia** passou a oferecer **apenas os paradigmas**
  (`grupo='paradigma'`), além dos que a própria análise já tinha selecionado
  (nada se perde). Método/disciplina/aplicação continuam no banco, classificados,
  fora daquele picker. **Método** já tem campo de texto próprio na Matriz.

Resultado: **106 → 43** termos no picker de Epistemologia.

## 3. Classificação atual dos 43 paradigmas (ativos)

Empirismo, Empirista, Empírica, Racionalismo, Racionalista, Materialismo,
Materialista, Positivista, Pós-Positivista, Construtivista, Neuroconstrutivista,
Fenomenológica, Pós-Estruturalista, Pragmática, Sócio-histórica, Sócio-Cultural,
Sócio-Cognitiva, Sociocognitiva, Sociocultural, Sócio-Histórica e Construtivista,
Multirreferencial, Multirreferencial e Polilógica, Teoria Polilógica,
Interpretativista, Crítica, Complexa, Sistêmica, Funcional-Sistêmica, Estrutural,
Histórica, Discursiva, Semiótica, Ontosemiótica, Social, Interdisciplinar,
Multidisciplinar, Teórica, Conceitual, Cognitiva, Evolutiva, Desenvolvimentista,
Política, Multirrefencial *(typo — unificar com Multirreferencial)*.

As demais facetas (para conferência/uso futuro): **metodologia** (23:
Qualitativa, Quantitativa, Experimental, Etnografia, Revisão, Meta-analítica,
Mista, Modelagem, Analítica, Descritiva…), **disciplina** (26: Linguística
Cognitiva, Neurociência Cognitiva, Psicologia Cognitiva, Matemática, Jurídica…),
**aplicacao** (11: Aplicada, Educacional, Design, Engenharia, Gestão, Saúde…),
**lixo** (3: "[Tópico não claro]", "Não identificada no texto", frase solta).

## 4. Pendências para a curadoria (ajuste fino)

O `grupo` é **editável termo a termo no admin**. Casos a revisar:
- **Unificar variantes** (fuzzy): Empirista/Empirismo; o cluster Sócio-*; "Multirrefencial" (typo) → Multirreferencial.
- **Fronteira paradigma × teoria:** "Semiótica"/"Ontosemiótica" podem ser melhor tratadas como teoria.
- **Enriquecer** com as referências nativas da AnCo hoje ausentes/marginais:
  Multirreferencialidade (Ardoino), Complexidade (Morin), Comunidades de
  prática/aprendizagem (Lave & Wenger), Sócio-histórico (Vygotsky), Espaços
  multirreferenciais de aprendizagem (Fróes). (Ver o doc da Matriz-Fróes.)

## 5. Como desfazer (se as coordenadoras não aprovarem)

```bash
# Limpa a faceta de todos os termos → o picker volta ao balaio de 106.
docker compose -f infra/docker-compose.yml exec web \
  python manage.py facetar_epistemologia --desfazer
docker compose -f infra/docker-compose.yml up -d --force-recreate web
```

A migration do campo `grupo` pode ficar (é inerte quando não usada) ou ser
revertida com `migrate vocabulario 0003`. **Nenhuma análise precisa ser tocada
para desfazer** — a facetação nunca alterou dados de análise nem o legado.

## 6. Reprocessar (após novos imports / ajustes de regra)

```bash
python manage.py facetar_epistemologia            # dry-run (mostra a classificação)
python manage.py facetar_epistemologia --apply
```
Idempotente. As regras vivem em `apps/acervo/management/commands/facetar_epistemologia.py`
(`_REGRAS` + `_OVERRIDES`).
