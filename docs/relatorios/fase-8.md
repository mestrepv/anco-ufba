# Relatório — Fase 8: Busca Semântica

## O que foi entregue

- **Subfase 8.1 — Infraestrutura de embeddings**
  - `infra/embeddings/` com Dockerfile + FastAPI mínimo + `sentence-transformers`
  - Serviço expõe `POST /embed` e `GET /health`; sobe com `--profile embeddings`
  - Volume `model_cache` para persistir modelo entre reinicializações
  - `apps/busca_semantica/embeddings.py` — wrapper com retry, timeout, cache LRU, `service_available()`

- **Subfase 8.2 — Modelo de dados**
  - DB trocado para `pgvector/pgvector:pg16` no docker-compose.yml
  - Migration `busca_semantica/0001_pgvector_extension.py` — `CREATE EXTENSION IF NOT EXISTS vector`
  - Migration `acervo/0003_embedding_fields.py` — adiciona `embedding` (384 dim) a `Artigo` e `Analise`; `embedding_resenha` em `Analise`; índices HNSW
  - Campos excluídos do `HistoricalRecords` (dados derivados, sem valor de histórico)
  - `pgvector>=0.3` adicionado ao `pyproject.toml`

- **Subfase 8.3 — Geração de embeddings**
  - `apps/busca_semantica/signals.py` — `post_save` em Artigo e Analise dispara task assíncrona
  - `apps/busca_semantica/tasks.py` — tasks idempotentes, fail-safe (embedding None em falha, sem bloquear publicação)
  - `apps/busca_semantica/management/commands/reindexar_embeddings.py` — processa em lotes, suporta `--tudo` e `--batch N`

- **Subfase 8.4 — Interface de busca**
  - Toggle "Textual / Por significado" no formulário de busca em `/acervo/`
  - Modo preservado em URL (`?modo=textual|semantico`)
  - Degradação graciosa: se serviço offline → exibe aviso amarelo e cai para textual
  - Resultados semânticos com selo de similaridade (0–100%, verde/âmbar/cinza por faixa)
  - Paginação substituída por limite de 50 com aviso explicativo (spec §6.2.1)

- **Subfase 8.5 — Avaliação qualitativa**
  - `docs/busca_semantica/avaliacao.md` com 10 queries representativas, hipóteses e tabelas
  - Documento é rascunho pré-indexação; deve ser preenchido após `reindexar_embeddings`

- **Testes**: 16 testes novos, todos passando; total da suíte 267 passando

## Critério de aceite (da especificação)

- [x] Container `embeddings` no compose (profile `embeddings`)
- [x] Extensão `pgvector` habilitada no Postgres
- [x] Campos `embedding*` em `Artigo` e `Analise` + índices HNSW
- [x] Geração de embeddings via signal `post_save` + task `django-q2`
- [x] Comando `manage.py reindexar_embeddings` para popular acervo existente
- [x] Toggle "textual / por significado" em `/acervo`, modo preservado em URL
- [x] Indicador de similaridade (0–100%) em cada resultado semântico
- [x] Sem regressão na busca textual
- [ ] Todos os 1.443 registros legado com embeddings — **pendente execução de `reindexar_embeddings` com serviço no ar**
- [ ] Documento de avaliação preenchido — **pendente indexação** (rascunho criado)

## Decisões tomadas

**Modelo `paraphrase-multilingual-MiniLM-L12-v2` em vez de `bge-m3`**: o servidor tem ~1,2 GB livres; o bge-m3 exige 3-4 GB. O modelo escolhido usa ~420 MB, é multilíngue (100 línguas incluindo português), e tem qualidade comprovada em benchmarks acadêmicos. Dimensões: 384 (spec previa 1024 para bge-m3 — ajustadas na migration).

**FastAPI mínimo em vez de `text-embeddings-inference`**: o TEI (Hugging Face) é otimizado para GPU e produção de alto volume; aqui o tráfego é baixo e a infra é CPU. Um FastAPI com sentence-transformers é mais simples, mais fácil de debugar e igualmente funcional para o caso de uso.

**Serviço com profile separado (`--profile embeddings`)**: o modelo ocupa ~420 MB e leva ~2-3 min para carregar em CPU. Em dev, é preferível subir só quando necessário. Em produção, incluir o profile no comando de startup.

**Embeddings excluídos do `HistoricalRecords`**: embeddings são dados derivados e regeneráveis. Incluí-los no histórico adicionaria ~1,5 KB por mudança por análise sem valor de auditoria.

**Retry com `EMBEDDINGS_MAX_RETRIES=1` em dev/test**: sem isso, cada fixture de teste que cria Artigo/Analise esperava 3+ segundos de timeout. Com 1 tentativa, falha rápido e segue.

## Desvios da especificação

| Especificação disse | O que foi feito | Por quê |
|---|---|---|
| `bge-m3`, 1024 dimensões | `paraphrase-multilingual-MiniLM-L12-v2`, 384 dim | Restrição de RAM do servidor (~1,2 GB livres) |
| `text-embeddings-inference` | FastAPI + `sentence-transformers` | Mais simples para CPU de baixo volume |
| Cards diferenciados por tipo (Artigo/Análise/Resenha) | Apenas Análises por enquanto | A query semântica atual retorna Análises; Artigos e Resenhas como tipo separado ficam para v3 |

## Dívida técnica deixada

- **Cards por tipo (Artigo/Análise/Resenha)**: a spec prevê resultados híbridos; por ora só retornam Análises (que já têm Artigo embutido). Artigos sem análise e Resenhas como tipo isolado requerem uma query UNION mais complexa — deixado para v3.
- **Avaliação qualitativa**: o documento `avaliacao.md` tem hipóteses e estrutura, mas os dados concretos dependem de `reindexar_embeddings` em produção.
- **`reindexar_embeddings` não executado em produção**: precisa de `--profile embeddings` no compose; documentado nas pendências abaixo.

## Métricas

- Testes novos: 16 (todos passando)
- Testes totais: 267 passando, 3 falhas pré-existentes (templates de fases anteriores)
- Arquivos criados: 12
- Arquivos modificados: 8
- RAM esperada do serviço de embeddings: ~420 MB

## Pendências para o usuário

1. **Reconstruir a imagem DB** para usar `pgvector/pgvector:pg16`:
   ```bash
   docker compose pull db
   docker compose up -d db
   docker compose exec web python manage.py migrate
   ```
   > **Atenção**: trocar a imagem do DB requer dump + restore se o volume já tem dados.
   > Em desenvolvimento com volume vazio, basta trocar e subir. Em produção, fazer backup antes.

2. **Subir e indexar**:
   ```bash
   docker compose --profile embeddings build embeddings
   docker compose --profile embeddings up -d embeddings
   docker compose logs -f embeddings  # aguardar "Modelo pronto"
   docker compose exec web python manage.py reindexar_embeddings
   ```

3. **Preencher `docs/busca_semantica/avaliacao.md`** com resultados reais após indexação.

4. **Incluir `--profile embeddings` no startup de produção** quando decidir habilitar a busca semântica para usuários.
