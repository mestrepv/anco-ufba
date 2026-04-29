# Adendo à Especificação AnCo — Fase 8: Busca Semântica

> Este adendo deve ser incorporado à `ESPECIFICACAO_ANCO_v2.md` como
> nova fase do roadmap (§10) e como ajustes nas seções §3 (Stack),
> §4 (Modelagem) e §6 (Acervo público).
>
> **Versão**: v2.1 — adiciona busca semântica como camada complementar à
> busca textual existente.

---

## Contexto da decisão

A busca semântica permite encontrar conteúdo por **significado**, não
por correspondência de palavras. Usuário busca *"trabalhos sobre
cognição em redes científicas"* e encontra textos sobre o tema mesmo
que usem termos como *"socio-cognitive analysis of scholarly
collaboration"* — sem precisar adivinhar o vocabulário do autor.

É a única aplicação de IA adotada na plataforma. Demais possibilidades
(pré-preenchimento de análises, detecção automática de pertinência,
sugestão de revisores, geração assistida de resenhas) foram
deliberadamente rejeitadas por incompatibilidade com os princípios de
autoria e revisão por pares da plataforma.

Busca semântica é um recurso de **acesso à informação**, não de
**produção de análise**. O usuário continua julgando a relevância; a
plataforma só ajuda a encontrar candidatos.

---

## Decisões arquiteturais

### Modelo de embeddings: local, não API
Modelo de embeddings open-source rodando em container próprio na VPS.
Sem dependência de API externa. Justificativas:
- Mantém a portabilidade da plataforma (princípio §9 da especificação).
- Zero custo recorrente.
- Sem questão de privacidade — nada sai da infraestrutura.
- Qualidade plenamente suficiente para textos acadêmicos.

**Modelo recomendado**: `BAAI/bge-m3` ou `intfloat/multilingual-e5-large`
— ambos suportam português nativamente, têm performance comparável aos
modelos comerciais, e geram embeddings de 1024 dimensões (bge-m3) ou
1024 (e5-large). Decisão final pelo Claude Code com base em RAM
disponível na VPS e benchmarks em amostras reais do acervo.

### Armazenamento: pgvector
Extensão `pgvector` do PostgreSQL. Embeddings ficam em colunas
`vector(N)` na própria base, junto aos dados. Vantagens:
- Não introduz novo serviço (Elasticsearch, Qdrant, Weaviate etc.).
- Backup do banco já cobre os embeddings.
- Queries semânticas em SQL puro com operadores `<=>` (similaridade
  cosseno) ou `<->` (distância euclidiana).
- Índices HNSW ou IVFFlat para performance.

### Modo de busca: toggle explícito
Interface oferece dois modos distintos:
- **Busca textual**: comportamento atual, full-text search do Postgres,
  ranking por relevância de termos.
- **Busca por significado**: busca semântica, ranking por similaridade
  vetorial.

Usuário escolhe explicitamente em radio button no topo do formulário
de busca. Ambos os modos respeitam as facetas laterais (ano, área,
epistemologia etc.).

Justificativa: transparência. Usuário sabe o que está usando, resultados
ficam interpretáveis, evita a "caixa-preta" de busca híbrida que
combina silenciosamente os dois.

### Escopo da indexação: tudo
Todos os campos textuais relevantes geram embeddings:

**Por Artigo:**
- `titulo` + `resumo` + `palavras_chaves` (concatenados como documento único)

**Por Análise:**
- `objeto` + `objetivo` + `foco` + `metodologia` + `resultados` +
  `aspectos_relevantes` + `definicao_extraida` + `referenciais`
  (concatenados como documento único)

**Por Resenha Crítica** (quando presente):
- `resenha_critica` (documento próprio, com peso destacado)

Cada um gera um vetor próprio. Busca pode retornar tanto Artigos
quanto Análises quanto Resenhas, com tipo identificado no resultado.

---

## 3. Adições à Stack (§3 da especificação)

### 3.1. Componentes adicionais
- **Modelo de embeddings**: `BAAI/bge-m3` (ou equivalente), em container
  próprio servido via `text-embeddings-inference` (Hugging Face) ou
  `sentence-transformers` em FastAPI mínimo.
- **Extensão pgvector**: instalada no container do Postgres.

### 3.2. Container adicional no `docker-compose.yml`
```
services:
  ...
  embeddings  → modelo de embeddings (CPU ou GPU se disponível)
                expõe HTTP interno para o web
```

### 3.3. Variável de ambiente nova
- `EMBEDDINGS_URL` (default `http://embeddings:8080`)
- `EMBEDDINGS_MODEL` (default `BAAI/bge-m3`)
- `EMBEDDINGS_DIMENSION` (default `1024`)

### 3.4. RAM adicional necessária
~3-4 GB para o modelo carregado em CPU. Se a VPS atual não comportar,
considerar upgrade ou usar modelo menor (`bge-small`, ~400 MB).

---

## 4. Adições à Modelagem (§4 da especificação)

### 4.1. Campos novos em modelos existentes

```python
from pgvector.django import VectorField

class Artigo(models.Model):
    # ... campos existentes ...
    embedding = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding semântico de titulo+resumo+palavras_chaves")
    embedding_atualizado_em = DateTimeField(null=True)

class Analise(models.Model):
    # ... campos existentes ...
    embedding = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding dos campos estruturais da análise")
    embedding_resenha = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding da resenha crítica (quando presente)")
    embedding_atualizado_em = DateTimeField(null=True)
```

### 4.2. Índices vetoriais
Migration adiciona índices HNSW sobre as colunas `embedding`:

```sql
CREATE INDEX idx_artigo_embedding ON acervo_artigo
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_analise_embedding ON acervo_analise
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_analise_embedding_resenha ON acervo_analise
    USING hnsw (embedding_resenha vector_cosine_ops);
```

### 4.3. Geração e atualização de embeddings
Tarefa assíncrona (django-q2):

- Disparada por *signal* `post_save` em Artigo e Análise.
- Gera embedding para o conteúdo concatenado relevante.
- Armazena vetor + timestamp.
- Em caso de falha do serviço de embeddings, marca para retry sem
  bloquear a publicação da análise.

Comando de management adicional:
```
manage.py reindexar_embeddings [--apenas-faltantes | --tudo]
```
Para regerar embeddings após mudança de modelo, ou popular após
migração inicial dos 1.443 registros legado.

---

## 5. Adições ao Acervo Público (§6 da especificação)

### 5.1. Toggle de modo de busca
Topo do formulário de busca em `/acervo`:

```
Modo de busca:
  ⦿ Textual         (encontra ocorrências exatas dos termos)
  ⦾ Por significado  (encontra conteúdo semanticamente relacionado)
```

Estado preservado em URL como parâmetro `?modo=textual|semantico`,
permitindo compartilhamento de URLs com modo definido.

### 5.2. Comportamento da busca semântica
1. Sistema gera embedding da query (chamada ao serviço de embeddings).
2. Executa três queries SQL paralelas (Artigos, Análises, Resenhas) com
   `ORDER BY embedding <=> query_embedding LIMIT N`.
3. Combina resultados com normalização de scores.
4. Aplica facetas selecionadas (ano, área etc.) como filtros sobre o
   conjunto.
5. Renderiza com cards distintos para cada tipo de resultado:
   *Artigo*, *Análise*, *Resenha Crítica*.

### 5.3. Indicador de relevância
Cada resultado da busca semântica exibe pontuação de similaridade
(0-100%). Evita o "achismo" sobre por que aquele resultado apareceu.

### 5.4. Limites e paginação
- Máximo 50 resultados por modo semântico (ranking decai rapidamente
  além disso).
- Paginação tradicional substituída por *limite com aviso*: "Mostrando
  os 50 resultados mais relevantes. Refine sua busca para resultados
  mais específicos."

---

## 6. Plano de implementação — Fase 8

> Inserir após Fase 7 (Polimento e produção).
>
> **Pré-requisito**: plataforma em produção, com acervo legado importado
> e pelo menos algumas análises feitas no novo fluxo.

### Fase 8 — Busca Semântica (3-4 dias)

**Subfase 8.1 — Infraestrutura de embeddings (1 dia)**
- Adicionar container `embeddings` ao `docker-compose.yml`.
- Configurar `text-embeddings-inference` ou equivalente.
- Health check do serviço.
- Wrapper Python no Django (`apps/busca_semantica/embeddings.py`) com
  retry, timeout e cache.

**Subfase 8.2 — Modelo de dados (0,5 dia)**
- Habilitar extensão pgvector.
- Adicionar campos `embedding*` aos modelos.
- Migration com índices HNSW.

**Subfase 8.3 — Geração de embeddings (1 dia)**
- Signal `post_save` em Artigo e Análise dispara task de embedding.
- Comando `reindexar_embeddings` para popular acervo existente
  (incluindo os 1.443 legado).
- Tratamento de falhas: marca registros sem embedding, retry programado.

**Subfase 8.4 — Interface de busca (1 dia)**
- Toggle de modo em `/acervo`.
- View de busca semântica.
- Cards diferenciados por tipo (Artigo/Análise/Resenha).
- Indicador de similaridade.
- Persistência do modo em URL.

**Subfase 8.5 — Avaliação qualitativa (0,5 dia)**
- Documento `docs/busca_semantica/avaliacao.md` com:
  - 10 queries representativas executadas em ambos os modos.
  - Comparação dos top-5 resultados.
  - Análise qualitativa: quando semântica ganha, quando textual ganha.
- Critério de aceite: para queries com termos não-óbvios
  (sinônimos, traduções), busca semântica retorna resultados
  pertinentes que a textual perde.

### Critério de aceite global da Fase 8
- Busca semântica funcionando ponta-a-ponta.
- Todos os 1.443 registros legado + análises novas com embeddings
  gerados.
- Documento de avaliação produzido.
- Sem regressão na busca textual.

---

## 7. Considerações que ficam de fora desta fase

- **Sugestão de "artigos relacionados"** na página de cada Artigo
  (usaria o mesmo embedding) — fica para v3.
- **Busca multilíngue** (query em inglês retorna resultados em
  português e vice-versa) — o modelo bge-m3 já suporta nativamente,
  mas a interface não expõe isso. Pode entrar como melhoria pequena.
- **Re-ranking com modelo cross-encoder** para top-N resultados —
  melhoria avançada, sem ROI claro no volume atual.
- **Análise de divergências entre análises do mesmo artigo** via
  similaridade vetorial — interessante metodologicamente para AnCo
  mas conceitualmente complexo. Avaliar para v3 com discussão prévia
  no grupo de pesquisa.

---

## 8. Atualização do histórico de versões

Adicionar à seção final da especificação:

- **v2.1** — Adiciona Fase 8 (Busca Semântica) como camada
  complementar opcional. Modelo de embeddings local (bge-m3 ou
  equivalente), pgvector como armazenamento, toggle explícito de modo
  textual/semântico, escopo de indexação cobrindo Artigos, Análises e
  Resenhas Críticas.

---

*Adendo gerado para integração à especificação após aprovação.*