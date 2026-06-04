# Plataforma AnCo — Especificação Técnica (v2.2)

> Documento de contrato técnico para implementação assistida por Claude Code.
>
> **Versão 2** — incorpora decisões sobre: ausência de upload de obras,
> resenha crítica como conteúdo autoral peer-reviewed em modalidade cega,
> licenciamento CC-BY-NC, verificação automática de links e estratégia
> de portabilidade entre hospedagens.
>
> **Versão 2.1** — adiciona busca semântica como camada complementar
> opcional (Fase 8): modelo de embeddings local (`bge-m3`), `pgvector`
> como armazenamento e toggle explícito textual/semântico no acervo.
>
> **Versão 2.2** — reescopagem da Fase 6: API REST genérica + Swagger
> adiados para v2 (sem cliente identificado justifica o custo). Em
> seu lugar, a fase entrega verificação periódica de links, changelist
> de links quebrados no admin, widgets de dashboard no admin home e
> JSON-LD (schema.org/ScholarlyArticle) embutido nas páginas — torna o
> acervo machine-readable sem novos endpoints.

---

## 1. Visão geral

### 1.1. Objetivo
Construir uma plataforma colaborativa de pesquisa para catalogar, analisar e
publicar análises de literatura científica sobre o conceito de **Análise
Cognitiva (AnCo)**, substituindo o fluxo atual baseado em Google Forms +
Sheets + Sites.

A plataforma é um **acervo de análises** (não um repositório de obras): as
obras analisadas são referenciadas exclusivamente por link; o conteúdo
hospedado é a análise estruturada produzida pelos pesquisadores e,
opcionalmente, uma resenha crítica autoral.

### 1.2. Princípios
- **Rigor científico**: análises só vão ao público após revisão por pares
  (double review). Resenhas críticas seguem revisão cega adicional.
- **Acervo permanente**: cada artigo e cada análise são citáveis, com URL
  estável.
- **Trabalho coletivo**: múltiplos analistas podem analisar o mesmo artigo;
  divergências são preservadas como dado, não como erro.
- **Transparência**: histórico de versões, autoria e revisões sempre visíveis.
- **Sustentabilidade**: open source, autohospedado, baixo custo operacional,
  portável entre hospedagens.
- **Integridade autoral e jurídica**: não hospeda obras de terceiros; só
  conteúdo originalmente produzido pela comunidade da plataforma.

### 1.3. Escopo desta especificação
Cobre arquitetura, modelagem, fluxos, migração, portabilidade e roadmap.
**Não cobre**: identidade visual elaborada, conteúdo institucional,
estratégia de divulgação.

---

## 2. Glossário

| Termo | Definição |
|-------|-----------|
| **AnCo** | Análise Cognitiva. Objeto de pesquisa do grupo. |
| **Artigo** | Publicação científica catalogada (livro, paper, capítulo). Um por DOI/identificador. **A obra em si nunca é hospedada na plataforma — apenas seu link de acesso.** |
| **Análise** | Avaliação estruturada de um Artigo segundo a grade AnCo (presença, pertinência, objeto, objetivo, metodologia etc.). Múltiplas por Artigo são permitidas (uma por analista). |
| **Resenha Crítica** | Texto autoral opcional do analista, com leitura crítica do Artigo. É conteúdo intelectual original, com revisão cega e selo de destaque no acervo. |
| **Revisão** | Parecer de um par sobre uma Análise submetida. |
| **Revisão Cega** | Modalidade aplicada exclusivamente à Resenha Crítica: o revisor não vê quem é o autor da resenha. |
| **Curador** | Usuário com poderes administrativos (gestão de vocabulários, aprovação de cadastros, gestão de legado, gestão de links quebrados). |
| **Analista** | Usuário ativo que cria análises e atua como revisor. |
| **Leitor** | Usuário cadastrado mas ainda não promovido a analista. |
| **Legado** | Os 1.443 registros importados da base atual, marcados como pré-validados. |
| **Vocabulário Controlado** | Listas canônicas de termos para campos como Epistemologia, Teoria, Área. |
| **Link Rot** | Fenômeno de links externos que se tornam inacessíveis com o tempo. Combatido por verificação automática e snapshots no Internet Archive. |

---

## 3. Stack técnica

### 3.1. Componentes
- **Backend**: Python 3.12 + Django 5.x + Django REST Framework
- **Banco**: PostgreSQL 16 + extensão `pgvector` (Fase 8)
- **Frontend**: Templates Django + HTMX + Alpine.js + Tailwind CSS
- **Busca textual**: PostgreSQL full-text search com `unaccent`
- **Busca semântica** (Fase 8): modelo de embeddings local
  (`BAAI/bge-m3` ou `intfloat/multilingual-e5-large`) servido em
  container próprio via `text-embeddings-inference`. Sem dependência de API
  externa — mantém portabilidade e zero custo recorrente.
- **Auth**: `django-allauth` com Google OAuth
- **Histórico de versões**: `django-simple-history`
- **Tarefas assíncronas**: `django-q2`
- **Reverse proxy + HTTPS**: Caddy 2 (Let's Encrypt automático)
- **Containerização**: Docker Compose
- **Backup**: `pg_dump` diário + sincronia para storage S3-compatible
  (cobre os embeddings, já que ficam na própria base)

### 3.2. Por que Django
- Admin nativo resolve gestão de curadoria sem código de UI custom.
- ORM maduro e bem documentado.
- Server-rendered facilita SEO e indexação no Google Scholar.

### 3.3. Estrutura de containers (`docker-compose.yml`)
```
services:
  web         → Django (gunicorn)
  db          → PostgreSQL 16 + pgvector (Fase 8)
  cache       → Redis (sessões, cache, fila de tasks)
  worker      → django-q2 worker
  caddy       → Reverse proxy + HTTPS
  embeddings  → modelo de embeddings (Fase 8, CPU ou GPU se disponível)
                expõe HTTP interno para o web
volumes:
  pgdata, caddy_data, caddy_config
networks:
  internal (web ↔ db ↔ cache ↔ worker ↔ embeddings)
  external (caddy ↔ web)
```

> **Nota Fase 8**: o serviço `embeddings` requer ~3-4 GB de RAM para o modelo
> em CPU. Se a VPS atual não comportar, considerar upgrade ou modelo menor
> (`bge-small`, ~400 MB).

> **Nota sobre volume `media`**: ausente intencionalmente. A plataforma
> não recebe upload de arquivos. Único conteúdo binário possível são
> avatares de usuário (opcional, baixa prioridade) — se implementado,
> volume separado e pequeno.

### 3.4. Variáveis de ambiente (`.env`)
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `BACKUP_S3_*` (bucket, chaves, endpoint)
- `BASE_URL` (para links em e-mails)
- `WAYBACK_API_ENABLED` (bool, default true)
- `EMBEDDINGS_URL` (Fase 8, default `http://embeddings:8080`)
- `EMBEDDINGS_MODEL` (Fase 8, default `BAAI/bge-m3`)
- `EMBEDDINGS_DIMENSION` (Fase 8, default `1024`)

---

## 4. Modelagem de dados

### 4.1. Diagrama conceitual
```
User ─┬─< Analise >─┬─ Artigo ─< SnapshotLink
      │             │
      └─< Revisao >─┘
                 │
                 └─ revisor (User, oculto em revisão cega)

Vocabulario ──< TermoVocabulario >── (referenciado em campos de Analise)
```

### 4.2. Modelos Django (esboço)

```python
class User(AbstractUser):
    nome_exibicao = CharField(max_length=200)
    vinculo_institucional = CharField(max_length=300)
    grupo_pesquisa = CharField(max_length=300, blank=True)
    orcid = CharField(max_length=19, blank=True)
    papel = CharField(choices=[('leitor','Leitor'),
                                ('analista','Analista'),
                                ('curador','Curador')],
                      default='leitor')
    aceita_revisoes = BooleanField(default=True)
    limite_revisoes_simultaneas = IntegerField(default=3)

class Artigo(models.Model):
    """
    Referência bibliográfica. NÃO armazena a obra em si — apenas
    metadados e links de acesso a fontes externas.
    """
    doi = CharField(max_length=200, unique=True, db_index=True,
                    help_text="DOI ou identificador interno determinístico")
    titulo = TextField()
    titulo_periodico = TextField()
    ano = IntegerField(null=True)  # validação: 1900 ≤ ano ≤ ano_corrente+1
    volume = CharField(max_length=50, blank=True)
    numero = CharField(max_length=50, blank=True)
    pagina_inicial = CharField(max_length=20, blank=True)
    pagina_final = CharField(max_length=20, blank=True)
    area = CharField(max_length=200, blank=True)
    autores = TextField()
    vinculacao_institucional = TextField(blank=True)
    palavras_chaves = TextField(blank=True)
    resumo = TextField(blank=True)
    base_consulta = ForeignKey(TermoVocabulario, related_name='+',
                                limit_choices_to={'vocabulario__codigo':'base'})

    # Acesso à obra (links externos apenas)
    link_acesso = URLField(help_text="Link primário para a obra")
    link_acesso_alternativo = URLField(blank=True,
        help_text="Repositório institucional, preprint, mirror")
    artigo_pago = BooleanField(default=False)
    acesso_aberto = BooleanField(default=False,
        help_text="Selo: obra com licença de acesso aberto")

    # Saúde dos links (gerenciado por tarefa assíncrona)
    link_status = CharField(max_length=20, default='nao_verificado',
        choices=[('nao_verificado','Não verificado'),
                  ('ok','OK'),
                  ('quebrado','Quebrado'),
                  ('redireciona','Redireciona')])
    link_ultima_verificacao = DateTimeField(null=True)

    # Embedding semântico (Fase 8) — pgvector
    embedding = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding de titulo+resumo+palavras_chaves")
    embedding_atualizado_em = DateTimeField(null=True)

    criado_em = DateTimeField(auto_now_add=True)

class SnapshotLink(models.Model):
    """Snapshot do link no Internet Archive (Wayback Machine)."""
    artigo = ForeignKey(Artigo, on_delete=CASCADE, related_name='snapshots')
    url_original = URLField()
    url_wayback = URLField()
    capturado_em = DateTimeField(auto_now_add=True)

class Analise(models.Model):
    STATUS = [
        ('rascunho', 'Rascunho'),
        ('submetida', 'Submetida para revisão'),
        ('em_revisao', 'Em revisão'),
        ('aprovada', 'Aprovada'),
        ('publicada', 'Publicada no acervo'),
        ('legado', 'Legado pré-validado'),
        ('despublicada', 'Despublicada'),
    ]
    artigo = ForeignKey(Artigo, on_delete=PROTECT, related_name='analises')
    analista = ForeignKey(User, on_delete=PROTECT, related_name='analises')
    status = CharField(max_length=20, choices=STATUS, default='rascunho')

    # Presença do termo AnCo
    presenca_titulo = BooleanField(null=True)
    presenca_resumo = BooleanField(null=True)
    presenca_palavras_chave = BooleanField(null=True)
    presenca_referencias = BooleanField(null=True)
    presenca_corpo = BooleanField(null=True)

    # Pertinência
    pertinencia = BooleanField(null=True)
    aspectos_relevantes = TextField(blank=True)
    define_conceito = BooleanField(null=True)
    definicao_extraida = TextField(blank=True)

    # Estrutura do artigo (extração estruturada — não autoral)
    objeto = TextField(blank=True)
    objetivo = TextField(blank=True)
    foco = TextField(blank=True)
    metodologia = TextField(blank=True)
    epistemologia = ManyToManyField(TermoVocabulario, related_name='+',
                                     limit_choices_to={'vocabulario__codigo':'epistemologia'})
    teoria = ManyToManyField(TermoVocabulario, related_name='+',
                              limit_choices_to={'vocabulario__codigo':'teoria'})
    referenciais = TextField(blank=True)
    resultados = TextField(blank=True)

    contexto_producao = TextField(blank=True)
    observacoes = TextField(blank=True)

    # === Conteúdo autoral original ===
    resenha_critica = TextField(blank=True,
        help_text="Texto crítico autoral. Quando preenchido, dispara "
                  "revisão cega adicional e ganha selo de destaque.")
    tem_resenha = BooleanField(default=False, db_index=True,
        help_text="Cache para filtros — atualizado por signal.")

    criado_em = DateTimeField(auto_now_add=True)
    submetida_em = DateTimeField(null=True)
    publicada_em = DateTimeField(null=True)

    # Embeddings semânticos (Fase 8) — vetores próprios para análise
    # estrutural e para a resenha crítica (quando presente).
    embedding = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding de objeto+objetivo+foco+metodologia+"
                  "resultados+aspectos_relevantes+definicao_extraida+referenciais")
    embedding_resenha = VectorField(dimensions=1024, null=True, blank=True,
        help_text="Embedding da resenha crítica, com peso destacado na busca")
    embedding_atualizado_em = DateTimeField(null=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            UniqueConstraint(fields=['artigo', 'analista'],
                             name='uniq_analise_por_analista_por_artigo')
        ]

class Revisao(models.Model):
    PARECER = [
        ('aprovar', 'Aprovar'),
        ('ajustes', 'Solicitar ajustes'),
        ('rejeitar', 'Rejeitar'),
    ]
    TIPO = [
        ('estrutural', 'Revisão estrutural (análise)'),
        ('cega', 'Revisão cega (resenha crítica)'),
    ]
    analise = ForeignKey(Analise, on_delete=CASCADE, related_name='revisoes')
    revisor = ForeignKey(User, on_delete=PROTECT, related_name='revisoes_feitas')
    tipo = CharField(max_length=15, choices=TIPO, default='estrutural')
    parecer = CharField(max_length=10, choices=PARECER, null=True)
    comentario_geral = TextField(blank=True)
    sorteado_em = DateTimeField(auto_now_add=True)
    prazo_em = DateTimeField()  # +14 dias para estrutural, +21 para cega
    concluido_em = DateTimeField(null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['analise', 'revisor', 'tipo'],
                             name='uniq_revisao_por_revisor_tipo')
        ]

class ComentarioRevisao(models.Model):
    revisao = ForeignKey(Revisao, on_delete=CASCADE, related_name='comentarios')
    campo = CharField(max_length=50)
    texto = TextField()

class Vocabulario(models.Model):
    codigo = SlugField(unique=True)
    nome = CharField(max_length=100)
    descricao = TextField(blank=True)

class TermoVocabulario(models.Model):
    vocabulario = ForeignKey(Vocabulario, related_name='termos')
    nome = CharField(max_length=200)
    descricao = TextField(blank=True)
    sinonimos = ArrayField(CharField(max_length=200), default=list)
    ativo = BooleanField(default=True)

class SolicitacaoCadastro(models.Model):
    usuario = OneToOneField(User, on_delete=CASCADE)
    justificativa = TextField()
    status = CharField(max_length=20, choices=[
        ('pendente','Pendente'), ('aprovada','Aprovada'), ('rejeitada','Rejeitada')])
    revisado_por = ForeignKey(User, null=True, related_name='+')
    revisado_em = DateTimeField(null=True)
```

### 4.3. Decisões importantes da modelagem

- **Artigo separado de Análise**: dois analistas podem analisar o mesmo
  artigo de ângulos diferentes. Restrição: cada *analista* só tem uma
  análise por *artigo*.
- **Sem `FileField`**: a plataforma não armazena obras. Apenas links.
  Evita questões autorais e mantém o storage perpetuamente pequeno.
- **`SnapshotLink`**: registra capturas no Wayback Machine como defesa
  contra link rot.
- **`resenha_critica` é apenas um campo de `Analise`**, não entidade
  separada. Razão: uma análise tem no máximo uma resenha (do mesmo
  autor da análise estrutural), e separar criaria complexidade
  desnecessária. O selo de destaque é derivado de `tem_resenha`.
- **`Revisao` tem campo `tipo`**: distingue revisão estrutural (vê
  autoria) de revisão cega (autoria oculta). Permite que a mesma
  análise tenha 2 revisões estruturais + 2 revisões cegas se houver
  resenha — ou apenas 2 estruturais se não houver.
- **Vocabulários controlados** evitam o "Empirismo" vs "empirismo" vs
  "Empírica" da base atual.
- **`HistoricalRecords`**: toda mudança em Análise gera versão consultável.
- **Embeddings semânticos (Fase 8)**: armazenados em colunas `vector(N)`
  com `pgvector`, indexados via HNSW (`vector_cosine_ops`). Gerados por
  signal `post_save` via task `django-q2`; falha do serviço de embeddings
  marca para retry sem bloquear publicação. Comando
  `manage.py reindexar_embeddings` regera após mudança de modelo.

---

## 5. Fluxos de usuário

### 5.1. Cadastro
1. "Entrar com Google" → OAuth → e-mail.
2. Validação de domínio contra *allowlist* (`*.edu`, `*.edu.br`, `*.ac.uk`,
   mais lista expansível: `ufba.br`, `ifba.edu.br`, `uneb.br`, `usp.br`,
   `unicamp.br`, `fiocruz.br`, `senaicimatec.com.br` etc.).
3. Domínio fora da lista → tela "domínio não autorizado, contato".
4. Domínio OK → cria User com papel `leitor`, mostra formulário de
   solicitação de promoção (vínculo institucional, grupo, justificativa).
5. Curadores notificados; aprovam ou rejeitam pelo admin.
6. Aprovação → papel vira `analista`, e-mail de boas-vindas com tour.

### 5.2. Criar análise
1. Analista busca artigo por DOI ou título no acervo.
2. Se artigo não existe, formulário "Cadastrar novo artigo" (metadados
   bibliográficos + **link de acesso obrigatório** + base de consulta).
3. Sistema valida o link (HEAD request) e oferece "Capturar snapshot no
   Internet Archive".
4. Sistema cria Análise vinculada, status `rascunho`.
5. Analista preenche formulário multipasso: Identificação +
   Presença/Pertinência + Estrutura + (opcional) Resenha Crítica.
   Auto-save a cada 30s.
6. Botão "Submeter para revisão" → status `submetida`, dispara sorteio.
   Sistema avisa: "Sua análise tem resenha crítica — ela passará por
   revisão cega adicional".

### 5.3. Sorteio de revisores
Trigger: análise muda para `submetida`.

Tarefa assíncrona executa:
1. **Sempre**: sorteia 2 revisores estruturais (regras já descritas:
   exclui autor, exclui autores de outras análises do mesmo artigo,
   respeita `aceita_revisoes` e `limite_revisoes_simultaneas`). Cria 2
   `Revisao(tipo='estrutural')` com prazo +14 dias.
2. **Se `tem_resenha`**: sorteia adicionalmente 2 revisores cegos,
   distintos dos estruturais. Cria 2 `Revisao(tipo='cega')` com prazo
   +21 dias. Na interface destes revisores, **autor é oculto** (campos
   `analista`, histórico de versões com nomes, comentários anteriores
   com autoria são todos mascarados como "Autor").
3. Status da análise vira `em_revisao`.
4. E-mails enviados (sem revelar autoria nos casos cegos).

**Fallback**: se < N revisores disponíveis (2 estruturais ou 2 cegos),
análise fica em fila de espera com flag visível para curadores.

**Cron diário**: revisões com `prazo_em < hoje` e `concluido_em IS NULL`
são re-sorteadas.

### 5.4. Revisar análise
1. Revisor acessa "Minhas revisões pendentes".
2. Vê análise lado a lado com formulário de revisão.
3. **Se revisão cega**: nome do autor mascarado em toda a interface;
   metadados temporais (datas) são mantidos; histórico de versões
   acessível mas com nomes anonimizados.
4. Adiciona comentário geral + comentários ancorados por campo.
5. Escolhe parecer e submete.

### 5.5. Publicação
- Análise vai para `aprovada` quando:
  - Análise sem resenha: 2 revisões estruturais com `aprovar`.
  - Análise com resenha: 2 estruturais + 2 cegas, todas `aprovar`.
- Tarefa pós-aprovação: status vira `publicada`, registra
  `publicada_em`, aparece no acervo público, autor recebe e-mail.
- Pareceres `ajustes` ou `rejeitar` seguem regras já descritas (volta
  para `rascunho` com comentários).

### 5.6. Gestão de legado (curadores)
- Tela "Acervo legado" lista os 1.443 registros importados.
- Filtros por analista, ano, base, status de revisão.
- Curador pode editar campos, marcar para revisão, despublicar.
- Análises legado ficam visíveis no acervo público com selo
  "Acervo histórico — pré-validado".

### 5.7. Gestão de saúde dos links (curadores)
- Tarefa periódica (semanal) executa HEAD em todos os `link_acesso` e
  `link_acesso_alternativo` de Artigos publicados.
- Resultado atualiza `link_status` e `link_ultima_verificacao`.
- Tela "Links quebrados" lista artigos com `link_status='quebrado'`.
- Curador pode: atualizar link manualmente, promover snapshot do
  Wayback como link primário, marcar como "indisponível
  permanentemente" (mantém visível com aviso).

---

## 6. Acervo público

### 6.1. Listagem (`/acervo`)
- Cards com título, autores, ano, periódico, analista(s),
  selos de status (Publicada, Legado, **Resenha Crítica** se aplicável).
- Paginação (20 por página).
- Ordenação: mais recentes / mais antigas / por ano de publicação /
  por título.

### 6.2. Busca facetada (estilo Tainacan)
- Caixa de busca textual (full-text em título, resumo, aspectos,
  definição, **resenha crítica**).
- **Toggle explícito de modo** (Fase 8): radio button no topo do
  formulário oferece "Textual" (FTS, default) ou "Por significado"
  (busca semântica via embeddings). Modo preservado em URL como
  `?modo=textual|semantico`. Sem busca híbrida silenciosa — usuário
  sempre sabe o que está usando.
- Facetas laterais com contagem (aplicadas em qualquer modo):
  - Ano de publicação (slider)
  - Base de consulta
  - Área
  - Epistemologia
  - Teoria
  - Pertinência (S/N)
  - Define conceito (S/N)
  - **Tem resenha crítica (S/N)**
  - Status (Publicada / Legado)
  - Acesso aberto (S/N)
  - Status do link (OK / Quebrado)
  - Analista
- URL refletindo facetas (compartilhável e citável).

### 6.2.1. Comportamento da busca semântica (Fase 8)
1. Sistema gera embedding da query (chamada ao serviço de embeddings).
2. Executa três queries SQL paralelas (Artigos, Análises, Resenhas)
   com `ORDER BY embedding <=> query_embedding LIMIT N`.
3. Combina resultados com normalização de scores.
4. Aplica facetas selecionadas como filtros sobre o conjunto.
5. Renderiza com **cards distintos por tipo**: *Artigo*, *Análise*,
   *Resenha Crítica*.
6. Cada resultado exibe **pontuação de similaridade (0-100%)**, evitando
   o "achismo" sobre por que apareceu.
7. Limite de 50 resultados (ranking decai rapidamente além disso); em
   vez de paginação tradicional, aviso "Mostrando os 50 mais relevantes
   — refine para resultados mais específicos".

### 6.3. Página do artigo (`/artigo/<id>`)
- Metadados bibliográficos completos.
- **Botões de acesso** (não download): "Acessar obra" → link primário;
  "Link alternativo" se houver; "Snapshot Wayback" se disponível;
  selo de "Acesso aberto" / "Acesso pago" conforme metadado.
- Lista de análises feitas sobre o artigo.
- Aviso visível se `link_status='quebrado'`.

### 6.4. Página da análise (`/analise/<id>`)
- Todos os campos preenchidos.
- Autoria visível (analista + revisores estruturais; revisores cegos
  aparecem como "Revisor cego A" e "Revisor cego B" sem identificação).
- **Resenha crítica em destaque** quando presente: card distinto, no
  topo da página, com selo "Resenha crítica peer-reviewed".
- Histórico de versões (link para diff).
- Botão "Citar esta análise" com formato ABNT/APA pré-formatado,
  incluindo DOI da plataforma se atribuído.
- **Aviso de licença CC-BY-NC** no rodapé da análise.

### 6.5. Acesso machine-readable (sem API REST dedicada)

A v1 não exporá uma API REST genérica (decisão da v2.2). Em vez disso,
adota duas vias mais leves:

- **JSON-LD embutido** (`<script type="application/ld+json">`) nas
  páginas de Artigo e Análise, com vocabulário `schema.org/ScholarlyArticle`.
  Indexável por Google Scholar, Zotero e agregadores acadêmicos.
- **Export individual** (BibTeX/RIS) — fica como melhoria pequena de
  v2 quando houver demanda concreta.

Uma API REST dedicada (`/api/v1/`) com `drf-spectacular` (Swagger)
permanece como item de v2, a ser implementada quando aparecer cliente
real (mobile, agregador, dashboard externo). Justificativa em §14.

---

## 7. Licenciamento

### 7.1. Conteúdo da plataforma
Todo conteúdo autoral hospedado (análises estruturadas, resenhas
críticas) é licenciado sob **Creative Commons Atribuição-NãoComercial
4.0 Internacional (CC-BY-NC 4.0)**.

Implicações:
- Reutilização permitida com atribuição.
- Uso comercial vedado sem autorização.
- Cada página de análise exibe o selo CC-BY-NC com link para a licença.
- Termos de uso da plataforma (a redigir antes do lançamento) explicitam
  que ao submeter conteúdo o autor concorda com este licenciamento.

### 7.2. Metadados bibliográficos
Metadados de Artigos (título, autores, DOI, ano etc.) são fatos
bibliográficos e ficam em domínio público / CC0.

### 7.3. Obras analisadas
**Não estão sob licenciamento da plataforma**. A plataforma apenas
referencia. A licença de cada obra é a definida por seu editor original.

---

## 8. Plano de migração da base existente

### 8.1. Inconsistências detectadas no JSON original
Limpeza necessária antes de importar:
- **Anos inválidos**: `21`, `218`, `2921` → `null` + flag para curador.
- **Nomes de analistas**: capitalização inconsistente
  (`GENIVALDO` vs Title Case) → normalizar via fusão admin.
- **Bases**: `scopus`/`SCOPUS`/`Scopus` → vocabulário canônico.
- **Campos S/N**: `S`/`N`/`Sim`/`Não`/`1`/`0` → `BooleanField` com null.
- **Campos vazios**: `""`/`"-"`/`"Não"` → distinguir intencional de vazio.
- **DOI**: vazios ou no formato `DOI: 10.xxxx` → normalizar; sem DOI,
  gerar identificador interno determinístico (hash de título+ano+periódico).
- **Links**: muitos registros sem `link_acesso`. Migração marca esses
  como **legado sem link** — visíveis no acervo com aviso "Link de
  acesso não disponível no acervo legado, considere contribuir
  atualizando este registro".

### 8.2. Estratégia de importação
1. **Script `migrate_legacy.py`** (management command Django):
   - Lê o JSON.
   - Normaliza campos.
   - Cria/recupera Artigo (deduplicação por DOI ou hash).
   - Cria User "legado" para analistas sem conta (papel `leitor`,
     e-mail placeholder, sem senha).
   - Cria Analise com status `legado`.
   - Loga normalização.
2. **Relatório de migração** (`migracao_relatorio.md`): totais,
   normalizações, rejeições, analistas criados.
3. **Reivindicação de autoria**: quando analista esperado se cadastra
   via Google e e-mail/nome bate, oferecer fusão com conta legado.

### 8.3. Idempotência
Script idempotente: rodar 2x não duplica. `update_or_create` com chave
determinística.

---

## 9. Estratégia de portabilidade

A plataforma será desenvolvida em VPS Ubuntu (sua) e posteriormente
migrada para hospedagem institucional (a definir). Decisões de
arquitetura para tornar essa migração trivial:

### 9.1. Tudo via variáveis de ambiente
Sem segredos hardcoded. `django-environ` lê `.env`. Migrar = trocar
`.env` e religar.

### 9.2. URLs canônicas e estáveis desde o dia 1
- Análises: `/analise/<id-imutável>/`
- Artigos: `/artigo/<doi-slug>/` (slug normalizado, sem `/` ou `?`)
- Identificadores nunca reaproveitados, mesmo em caso de despublicação.

### 9.3. Plano de redirecionamento na migração
Quando migrar do domínio temporário para o oficial, configurar no Caddy
do domínio antigo: `redir https://novo-dominio.tld{uri} permanent`.
Manter por no mínimo 12 meses para honrar citações já feitas.

### 9.4. Conversa com TI institucional
Antes da Fase 7 (deploy em produção), iniciar conversa com a TI da
instituição hospedeira. Pergunta concreta: *"Tenho uma aplicação
Django em containers Docker. Como funciona o processo de hospedagem?"*.
Resposta calibra: aceita Docker direto, exige stack tradicional, ou
oferece infraestrutura própria.

### 9.5. Backup como contrato
- `pg_dump` diário, retenção local 7 dias, remota 90 dias.
- **Restore testado em staging trimestralmente.**
- Sem este teste, a migração futura é a primeira vez que o backup é
  exercitado de verdade — e aí mora o desastre.

---

## 10. Roadmap de implementação em fases

> **Importante**: implementar fase por fase, com commits separados e
> validação humana ao fim de cada fase.

### Fase 0 — Fundação (1 dia)
- Estrutura Django + Docker Compose.
- Postgres, Redis, Caddy.
- Settings dividido (base/dev/prod).
- CI: lint (ruff) + testes (pytest-django).
- README com bootstrap local.

### Fase 1 — Núcleo de dados e admin (2-3 dias)
- Modelos completos (incluindo `SnapshotLink` e campo `resenha_critica`).
- Migrations.
- Admin Django configurado.
- `django-simple-history` integrado.
- Vocabulários iniciais via fixture.
- Script `migrate_legacy.py` funcionando para 1.443 registros.
- **Aceite**: `manage.py migrate_legacy` importa tudo; admin navegável.

### Fase 2 — Autenticação e cadastro (1-2 dias)
- `django-allauth` + Google OAuth.
- Validação de domínio.
- Tela de solicitação de promoção.
- Notificação aos curadores.
- **Aceite**: você se loga, solicita promoção, é aprovado por curador.

### Fase 3 — Criação e edição de análises (3-4 dias)
- Busca/criação de Artigo com validação de link.
- Integração Wayback Machine (botão "Capturar snapshot").
- Formulário multipasso (HTMX).
- **Quarto passo opcional**: Resenha Crítica.
- Auto-save.
- Submissão para revisão.
- **Aceite**: criar análise completa do zero, com e sem resenha.

### Fase 4 — Fluxo de revisão por pares (3-4 dias)
- Sorteio automático: 2 estruturais + 2 cegos (se há resenha).
- Tela "Minhas revisões pendentes" com mascaramento de autoria
  para revisões cegas.
- Formulário de revisão com comentários ancorados.
- Lógica de transição de status (todas as combinações).
- Re-sorteio por prazo.
- **Aceite**: análise com resenha passa por 4 revisões, autoria
  preservadamente oculta nas cegas, é publicada automaticamente.

### Fase 5 — Acervo público (3-4 dias)
- Listagem com paginação.
- Busca facetada (Postgres FTS + facetas dinâmicas).
- Páginas de Artigo e Análise.
- Selo de destaque para resenhas críticas.
- Histórico de versões consultável.
- Geração de citação ABNT/APA.
- Selo CC-BY-NC visível.
- **Aceite**: navegar, buscar e citar análises sem login.

### Fase 6 — Saúde de links, dashboard e acesso machine-readable (1-2 dias)

**Reescopada na v2.2.** Foco em valor concreto sem custo de manter
uma API REST sem cliente.

- **Tarefa periódica de verificação de links** (cron semanal via
  `django-q2 Schedule`): itera artigos publicados e legados, faz HEAD
  via `apps.acervo.services.validar_link` (já existente da Fase 3),
  atualiza `link_status` e `link_ultima_verificacao`.
- **Changelist "Links quebrados"** no admin: filtro pré-aplicado por
  `link_status='quebrado'` + actions em lote (atualizar link manual,
  promover snapshot Wayback como link primário, marcar
  "indisponível permanentemente").
- **Widgets de dashboard no admin home**: totais por status de
  análise, quantidade de revisões pendentes/atrasadas, quantos
  artigos com link quebrado, quantas solicitações de cadastro
  pendentes. Reaproveita o admin do Django (sem tela custom).
- **JSON-LD nas páginas públicas** (`schema.org/ScholarlyArticle`):
  metadados estruturados embutidos em `/artigo/<slug>/` e
  `/analise/<id>/` para Scholar/Zotero/agregadores consumirem
  diretamente o HTML.

Adiados para v2 (ver §14): API REST dedicada e Swagger
(`drf-spectacular`).

### Fase 7 — Polimento e produção (2 dias)
- Backup automatizado (pg_dump → S3-compatible).
- Logs estruturados.
- Monitoring básico (Sentry self-hosted ou GlitchTip).
- Páginas estáticas (Sobre, Equipe, Termos de Uso, Política de Privacidade).
- Deploy em produção.

### Fase 8 — Busca semântica (3-4 dias)

> **Pré-requisito**: plataforma em produção (Fase 7 concluída) com
> acervo legado importado e algumas análises feitas no fluxo novo.

**Subfase 8.1 — Infraestrutura de embeddings (1 dia)**
- Container `embeddings` no `docker-compose.yml` (`text-embeddings-inference`
  ou `sentence-transformers` em FastAPI mínimo).
- Health check do serviço.
- Wrapper Python (`apps/busca_semantica/embeddings.py`) com retry,
  timeout e cache.

**Subfase 8.2 — Modelo de dados (0,5 dia)**
- Habilitar extensão `pgvector`.
- Adicionar campos `embedding*` aos modelos.
- Migration com índices HNSW (`vector_cosine_ops`).

**Subfase 8.3 — Geração de embeddings (1 dia)**
- Signal `post_save` em Artigo e Análise dispara task de embedding.
- Comando `manage.py reindexar_embeddings [--apenas-faltantes | --tudo]`
  para popular acervo existente (incluindo os 1.443 legado).
- Tratamento de falhas: marca registros sem embedding, retry programado.

**Subfase 8.4 — Interface de busca (1 dia)**
- Toggle de modo em `/acervo` (textual / por significado).
- View de busca semântica.
- Cards diferenciados por tipo (Artigo / Análise / Resenha).
- Indicador de similaridade (0-100%).
- Persistência do modo em URL (`?modo=textual|semantico`).

**Subfase 8.5 — Avaliação qualitativa (0,5 dia)**
- Documento `docs/busca_semantica/avaliacao.md` com:
  - 10 queries representativas executadas em ambos os modos.
  - Comparação dos top-5 resultados.
  - Análise qualitativa: quando semântica ganha, quando textual ganha.

**Aceite global da Fase 8**:
- Busca semântica funcionando ponta-a-ponta.
- Todos os 1.443 registros legado + análises novas com embeddings.
- Documento de avaliação produzido.
- Sem regressão na busca textual.

**Justificativa**: a busca semântica é a única aplicação de IA adotada.
Demais possibilidades (pré-preenchimento de análises, detecção
automática de pertinência, sugestão de revisores, geração assistida
de resenhas) foram **deliberadamente rejeitadas** por incompatibilidade
com os princípios de autoria e revisão por pares da plataforma. Busca
semântica é recurso de **acesso à informação**, não de **produção de
análise**.

**Fora de escopo da Fase 8** (avaliar para v3):
- "Artigos relacionados" na página de cada Artigo.
- Busca multilíngue exposta na interface (o `bge-m3` suporta nativamente).
- Re-ranking com cross-encoder.
- Análise de divergências entre análises do mesmo artigo via similaridade.

**Total estimado**: ~3 a 4 semanas para as Fases 0-7 + 3-4 dias para a Fase 8 (opcional).

---

## 11. Estratégia de testes

### 11.1. Cobertura mínima
- **Unitários**: validações de modelo, normalização do migrador,
  validação de domínio.
- **Integração**: fluxo análise simples (criar → submeter → 2 revisões
  estruturais → publicar); fluxo análise com resenha (criar → submeter
  → 2 estruturais + 2 cegas → publicar); mascaramento de autoria em
  revisão cega.
- **Regressão**: importação do JSON legado produz N registros conhecidos.

### 11.2. Ferramentas
- `pytest-django` + `pytest-factoryboy`.
- `coverage.py`.
- Meta inicial: 70% em `models.py`, `views.py`, `services.py`.

---

## 12. Backup e recuperação

### 12.1. Estratégia
- `pg_dump` diário às 03:00, retenção local 7 dias.
- Sincronia para storage S3-compatible, retenção remota 90 dias.
- Backup mensal arquivado indefinidamente.
- **Sem volume de mídia para sincronizar** (consequência positiva da
  decisão de não hospedar arquivos).

### 12.2. Teste de restore
Documentar em `RESTORE.md`. Testar em staging trimestralmente.

---

## 13. Considerações de segurança

- HTTPS obrigatório (Caddy + Let's Encrypt).
- `SECURE_*` settings ativos em produção.
- CSP restritiva.
- Rate limiting em busca e API (`django-ratelimit`).
- Validação anti-SSRF na verificação automática de links (HEAD requests
  com timeout, sem seguir redirects para IPs internos, sem ler corpo
  da resposta).
- Backup de chaves OAuth fora do repo.
- Log de acesso ao admin retido por 90 dias.

---

## 14. Itens deliberadamente fora do escopo inicial

- Identidade visual elaborada.
- App mobile.
- Integração com ORCID além de campo de cadastro.
- Exportação BibTeX/RIS — fica para v2.
- Notificações in-app em tempo real.
- Internacionalização (só pt-BR para v1).
- **Hospedagem de arquivos de qualquer natureza além de avatares
  opcionais** (decisão estrutural).
- DOI próprio para análises (avaliar com PPGDC para v2).
- **API REST dedicada (`/api/v1/`) e Swagger via `drf-spectacular`** —
  adiada na v2.2. Justificativa: sem cliente identificado (sem mobile,
  sem dashboard externo, sem integração planejada), o custo de manter
  uma API genérica supera o benefício. O acervo continua machine-readable
  via JSON-LD embutido nas páginas (§6.5). Implementar quando surgir
  cliente real.

---

## 15. Próximos passos

1. Revisar este documento e marcar ajustes.
2. Definir **nome próprio** para a plataforma.
3. Criar repositório Git.
4. Colar este documento como `docs/ESPECIFICACAO.md`.
5. Colar `CLAUDE.md` na raiz.
6. Abrir Claude Code: *"Leia `docs/ESPECIFICACAO.md` e `CLAUDE.md`,
   implemente a Fase 0, pare ao final aguardando minha aprovação."*

---

## Histórico de versões

- **v1** — Versão inicial.
- **v2** — Sem upload de arquivos; resenha crítica peer-reviewed cega
  como conteúdo autoral original; licença CC-BY-NC; verificação
  automática de links + Wayback Machine; seção dedicada de portabilidade.
- **v2.1** — Adiciona Fase 8 (Busca Semântica) como camada complementar
  opcional. Modelo de embeddings local (`bge-m3` ou equivalente),
  `pgvector` como armazenamento, toggle explícito textual/semântico,
  escopo de indexação cobrindo Artigos, Análises e Resenhas Críticas.
  Adendo de origem em `docs/fase8_adendo.md` (mantido como artefato
  histórico).
- **v2.2** — Reescopagem da Fase 6. API REST dedicada (`/api/v1/`) e
  Swagger (`drf-spectacular`) movidos para v2 (§14): sem cliente real
  identificado, custo de manutenção não se justifica. Em seu lugar, a
  Fase 6 agora entrega: verificação periódica de links via cron,
  changelist "Links quebrados" no admin com actions em lote, widgets
  de dashboard no admin home e JSON-LD (schema.org/ScholarlyArticle)
  embutido nas páginas públicas — torna o acervo machine-readable sem
  novos endpoints.

---

*Documento mantido vivo. Cada versão futura deve atualizar o histórico.*
---

## Addendum — desvio do fluxo de revisão (2026-06)

As seções 5.3–5.6 descrevem o fluxo **original** de revisão por pares das
análises (2 revisores estruturais + 2 cegos quando há resenha; publicação
automática por consenso). Esse fluxo foi **substituído** a pedido do produto:

- **Análises não passam mais por revisão por pares.** Uma entrada entra no
  acervo somente após **aprovação de um curador** (fila em `/acervo-analista/curadoria/`).
  Estados da `Analise`: `rascunho → submetida → (curador) publicada`; o curador
  pode pedir ajustes (`→ rascunho`) ou rejeitar (`→ rejeitada`).
- **A revisão cega por pares vale só para a resenha crítica**, agora uma
  entidade própria (`Resenha`, 1:1 com `Analise`). Ciclo: `rascunho → submetida
  → em_revisao → revisada → (curador confirma) publicada`. A resenha só aparece
  no acervo após confirmação da curadoria; a publicação da análise é independente.

Detalhes de implementação: `apps/acervo/{models,sorteio,aprovacao,signals,tasks,views}.py`.

---

## Addendum — Fase 9: Triagem PRISMA-ScR (app `apps/triagem`)

Etapa **anterior à análise** (upstream da Matriz AnCo): seleção de fontes
reprodutível e reportável segundo o **PRISMA-ScR**. Decisão de produto
(2026-06): construir como **app nativo** `apps/triagem`, **aditivo** (tabelas
novas; **sem alterar o schema de `acervo`**).

Fluxo dos **novos analistas**: **busca em ≥9 bases** (reusa o vocabulário `base`
já existente) → **importação por arquivo** (RIS/BibTeX/CSV) com dedup → **triagem
por ≥2 revisores independentes** (incluir/excluir/dúvida + motivo), divergência
resolvida por terceiro/curador → **promoção dos incluídos a `Artigo`** → análise
pela Matriz AnCo (fluxo de `Analise` já existente).

- **Isenção do legado:** o acervo histórico (`Analise.status = legado`, base de
  fundação curada por Eneida Santana) **não passa por triagem**. A triagem só cria
  `Artigo` **novos**; candidato que casa com `Artigo` existente (inclusive legado)
  é marcado `ja_no_acervo` e não é re-triado nem duplicado.
- **Modelos:** `ProtocoloTriagem` (singleton), `Busca` (por base, contagem PRISMA),
  `RegistroTriagem` (candidato pré-`Artigo`, dedup determinístico), `DecisaoTriagem`
  (parecer de 1 revisor, análogo a `Revisao`).
- **Infraestrutura reusada (espelhada, não generalizada):** sorteio/avaliação/
  sinais/tasks de revisão cega de `apps/acervo` → `apps/triagem`, para não
  desestabilizar a revisão de resenha já testada.
- **PRISMA-ScR:** contagens (identificados/duplicados/triados/incluídos/excluídos
  por motivo) e fluxograma derivados dos status de `RegistroTriagem`.

Entregue em sub-fases (9.0 scaffolding → 9.6 PRISMA), uma por vez, com relatório de
fim de fase e aprovação humana. Plano: `docs/relatorios/fase-9.md`.
