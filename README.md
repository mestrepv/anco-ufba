# AnCo — Plataforma de Análise Cognitiva

Plataforma colaborativa de pesquisa para **catalogar, analisar criticamente e
difundir** literatura científica sobre **Análise Cognitiva (AnCo)**. Substitui um
fluxo legado baseado em Google Forms + Sheets + Sites por um sistema com cadastro
aberto, vocabulário controlado, **aprovação editorial por curadoria**, **revisão
cega por pares das resenhas críticas** e acervo público citável, com busca textual
facetada e busca semântica.

- **URL pública:** <https://anco.paulovicente.pro.br/>
- **Stack:** Python 3.12 · Django 5.x · PostgreSQL 16 + pgvector · Redis 7 ·
  django-q2 · Caddy 2 · Docker Compose · HTMX/Alpine/Tailwind
- **Licença:** código em **AGPL-3.0-or-later**; conteúdo autoral em **CC BY-NC 4.0**
- **Repositório:** <https://github.com/mestrepv/anco-ufba>

> Documento de apoio a **resumo expandido / artigo** submetido a congresso de
> difusão do conhecimento. Contrato técnico canônico em
> [docs/especificacao/ESPECIFICACAO.md](docs/especificacao/ESPECIFICACAO.md) (ver o *addendum* ao final, que
> registra a mudança do fluxo de revisão). Fundamentação conceitual em
> [docs/metodo/tutorial-base-anco.md](docs/metodo/tutorial-base-anco.md).

---

## Sumário

1. [Objetivo do sistema](#1-objetivo-do-sistema)
2. [Contexto e motivação — de planilha a plataforma](#2-contexto-e-motivação--de-planilha-a-plataforma)
3. [Modelagem de dados](#3-modelagem-de-dados)
4. [Fluxo de uso](#4-fluxo-de-uso)
5. [Aspectos metodológicos](#5-aspectos-metodológicos)
6. [Busca semântica](#6-busca-semântica)
7. [Stack tecnológica — vantagens, desvantagens e substitutos](#7-stack-tecnológica--vantagens-desvantagens-e-substitutos)
8. [Dois modos por projeto: Triagem PRISMA-ScR (rigoroso) e Revisão ANCO (simplificado)](#8-dois-modos-por-projeto-triagem-prisma-scr-rigoroso-e-revisão-anco-simplificado)
9. [Bootstrap local e comandos](#9-bootstrap-local-e-comandos)
10. [Como citar, autoria e licença](#10-como-citar-autoria-e-licença)

---

## 1. Objetivo do sistema

A AnCo (plataforma) tem por objetivo **transformar a catalogação dispersa de
literatura científica em um acervo metodologicamente rigoroso, colaborativo e
citável**, voltado ao campo da **Análise Cognitiva** — abordagem epistemológica
multirreferencial para investigar os processos cognitivos de sujeitos engajados
na construção e difusão do conhecimento.

Objetivos específicos:

1. **Catalogar** referências bibliográficas (a plataforma nunca hospeda a obra —
   apenas metadados e link de acesso) sob identificação estável e sem duplicatas.
2. **Estruturar a análise** de cada obra segundo uma grade conceitual comum
   (presença do termo, pertinência, objeto, objetivo, foco, metodologia,
   epistemologia, teoria, resultados), tornando **explícito no banco** o que era
   implícito e perdido na planilha.
3. **Preservar a pluralidade interpretativa**: múltiplos analistas podem analisar
   o mesmo artigo com lentes distintas — divergências são **dado de pesquisa**, não
   conflito de edição.
4. **Garantir qualidade editorial** por **aprovação de curadoria** (para a entrada
   no acervo) e por **revisão cega por pares** (para a resenha crítica autoral).
5. **Difundir** o conhecimento por um acervo público, com URLs estáveis citáveis
   (ABNT/APA), busca facetada e busca semântica, sob licença aberta.

---

## 2. Contexto e motivação — de planilha a plataforma

A pesquisa em Análise Cognitiva no PPGDC vinha organizada em um pipeline
**Google Forms → Sheets → Sites**, acumulando ~**1.443 registros** ao longo de
várias coortes. A inspeção desse acervo (documentada em
[docs/migracao/](docs/migracao/)) mostrou que o problema não era cosmético, mas
**metodológico**: anos inválidos (`21`, `2921`), capitalização não normalizada de
analistas (duplicatas funcionais), campos S/N com seis grafias, ausência ambígua
(vazio/"-"/"Não" misturados), DOIs malformados, links faltantes e variantes de
base e de termos epistemológicos tratadas como entradas distintas.

Mais do que limpeza de dados, esses sintomas evidenciaram que a planilha **não
suporta a metodologia que a AnCo exige**: não há revisão, histórico de versões,
integridade referencial, busca facetada, URL citável; e divergências viram
conflitos de edição. A plataforma é a resposta a esse diagnóstico.

**Decisão sobre o acervo de fundação:** a importação direta dos 1.443 registros
brutos foi **descartada**. Em vez de carregar a plataforma com dados não
confiáveis, a equipe partiu de uma **base revisada e curada bibliograficamente**
— `base-anco-revisada.json`, **653 registros** —,
submetida à **curadoria da bibliotecária e Doutora em Difusão do Conhecimento
Eneida Santana** (equipe fundadora). Essa base curada constitui o **acervo de
fundação** (status `legado`), sobre o qual o fluxo novo (cadastro aberto +
curadoria editorial) passa a operar. A carga é **idempotente e auditável**
(`manage.py migrate_base_revisada`).

---

## 3. Modelagem de dados

Detalhes em [apps/acervo/models.py](apps/acervo/models.py),
[apps/core/models.py](apps/core/models.py) e
[apps/vocabulario/models.py](apps/vocabulario/models.py).

```
  User ──< Análise >── Artigo ──< SnapshotLink
   │         │  1:1                  │ FK/M2M
   │         │                       └─ TermoVocabulario (base, epistemologia, teoria)
   │      Resenha ──< Revisão (cega) >── User (revisor)
   └─ SolicitacaoCadastro (promoção a analista/revisor)
```

- **`User`** — papéis `leitor`, `analista`, `curador`; vínculo institucional,
  ORCID, foto; flags de revisor (`aceita_revisoes`, `revisor_aprovado`,
  `limite_revisoes_simultaneas`).
- **`Artigo`** — referência bibliográfica. Identificação em três níveis com
  `UniqueConstraint`: **DOI → ISBN → identificador interno determinístico**
  (`legacy:<hash16>` de título+ano+periódico). Campos `area` (grande área
  **CNPq/CAPES**, menu fechado), `idioma`, `base_consulta` (vocabulário),
  `link_status`, `acesso_aberto`.
- **`Análise`** — avaliação estruturada de um Artigo. Constraint `(artigo,
  analista)` = uma análise por par. Estados: `rascunho → submetida → publicada`
  (por curadoria), com `rejeitada` e `despublicada`. Campos de curadoria
  (`aprovada_por/em`, `motivo_curadoria`) e de despublicação (`despublicada_por/em`,
  `status_pre_despublicacao`).
- **`Resenha`** — **entidade própria** (1:1 com Análise), o componente autoral
  crítico. Ciclo independente: `rascunho → submetida → em_revisao → revisada →
  publicada` (esta última por confirmação de curadoria). Só ela passa por revisão
  por pares.
- **`Revisão` / `ComentarioRevisao`** — parecer cego (`aprovar`/`ajustes`/`rejeitar`)
  **sobre a Resenha** (não mais sobre a análise), com prazo, sorteio e comentários.
- **`Vocabulario` / `TermoVocabulario`** — listas canônicas (base, epistemologia,
  teoria) com `sinonimos` (ArrayField) e `buscar_canonico()` para colapsar
  variantes ortográficas no termo canônico.
- **`SnapshotLink`** — captura no Internet Archive contra *link rot*.
- **Auditoria**: toda Análise e Resenha é versionada via `django-simple-history`
  (exclui só campos derivados, como embeddings).

**Camada de triagem (`apps/triagem`, aditiva — não toca o schema do acervo):**

```
  ProtocoloTriagem (= projeto, modo: rigoroso|anco) ──< ProjetoMembro >── User (papel por projeto)
        │  │  │
        │  │  └─< Busca (importação: base, arquivo, filtros, contagens, criado_por)
        │  └────< RegistroTriagem ──< DecisaoTriagem >── User (revisor, por etapa)
        │              └─ FK Artigo (proveniência: só os incluídos viram Artigo)
        ├─< SnapshotProtocolo · RodadaCalibracao            (modo rigoroso)
        └─< SorteioAnalise ──< AtribuicaoAnalise >── User   (modo ANCO)
                  └─ ConsensoAnalise (revisão dupla)
```

- **`ProtocoloTriagem`** = **o projeto** (revisão de escopo): `nome/slug`, pergunta,
  `estrategia_busca`, critérios de inclusão/exclusão, `n_revisores`/prazo, `versao`/
  `travado_em` (protocolo a priori), `registro_externo` (OSF), `usa_texto_completo`.
  **`modo`** comuta o fluxo do projeto entre **`rigoroso`** (PRISMA-ScR, Fases 9–12)
  e **`anco`** (Revisão ANCO simplificada, Fase 13) — default `rigoroso`; ver §8.
- **`ProjetoMembro`** — vínculo usuário↔projeto com **papel por projeto** (analista/curador).
- **`Busca`** — uma importação (base, arquivo cru, filtros, contagens de dedup, **`criado_por`**).
- **`RegistroTriagem`** — candidato pré-`Artigo` (`identificado → em triagem → incluído/
  excluído/duplicado`); dedup determinística + `pg_trgm`; proveniência em `artigo`.
  `relevancia_score` cacheia, no modo ANCO, a correspondência de termos da estratégia de
  busca (sem embeddings), para ordenar a lista de incluídos.
- **`DecisaoTriagem`** — parecer de um revisor por **etapa** (título/resumo, texto completo
  ou calibração); concordância **κ de Fleiss**.
- **`SnapshotProtocolo`**, **`RodadaCalibracao`**, **`ParDuplicataDescartado`** — versão a
  priori congelada, piloto de calibração e pares marcados como **não**-duplicata (modo rigoroso).
- **`SorteioAnalise` / `AtribuicaoAnalise` / `ConsensoAnalise`** (modo ANCO) — distribuição
  da análise por **cota** (5/analista), em revisão **única** ou **dupla** (`modo_revisao`);
  cada `AtribuicaoAnalise` liga analista↔artigo; na dupla, `ConsensoAnalise` registra a
  conciliação das duas análises independentes pelo curador.

---

## 4. Fluxo de uso

### 4.1. Cadastro e papéis (cadastro aberto)

1. **Login** via Google OAuth — **qualquer conta** entra como `leitor`.
2. **Promoção a analista**: no `/perfil/`, o leitor preenche dados e marca
   "Quero ser analista", criando uma `SolicitacaoCadastro` pendente.
3. **Curadoria aprova** a solicitação (admin) → o usuário vira `analista` e pode
   criar análises. (Habilitação como revisor é análoga.)

### 4.2. Entrada de artigos: importação + triagem (dois modos por projeto)

O analista **não cadastra mais artigos um a um por DOI**. A entrada agora é por
**importação de arquivo**, dentro de um **projeto** de revisão de escopo
(`/triagem/p/<slug>/`). Cada projeto é criado em um de **dois modos** (`modo`,
default `rigoroso`), que comuta o fluxo de seleção **sem remover** o outro:

**Comum aos dois modos:**

1. **Importa** o arquivo de exportação da base — **RIS / BibTeX / CSV** — ou, para
   bases sem exportação direta (ex.: repositórios institucionais), usa o **Zotero**
   como ponte e exporta em RIS.
2. O sistema **deduplica** automaticamente (DOI > ISBN > hash) e lista **possíveis
   duplicatas** por similaridade de título para confirmação humana (com trilha de
   auditoria e reversão). Quem já casa com o acervo — inclusive o **legado** — é
   marcado e **isento** de triagem.

**Modo `rigoroso` (Triagem PRISMA-ScR):** o **curador inicia a triagem**; cada
registro é sorteado para **≥2 revisores membros**, que decidem **incluir / excluir /
dúvida** numa interface **mascarada** (cega ao coletor e aos pares). **Consenso**
resolve; **divergência** vai a **desempate** do curador. (Opcional por projeto: 2
etapas, título/resumo → texto completo; calibração-piloto e protocolo a priori.)

**Modo `anco` (Revisão ANCO simplificada):** reproduz o fluxo da disciplina de
Análise Cognitiva. O **dono da base autotria** seus próprios registros
(incluir/excluir, revisor único); os **incluídos** ficam em uma lista **ordenada por
relevância** (correspondência de termos da estratégia de busca, sem embeddings); e o
curador roda um **sorteio de análise** que distribui uma **cota (5 por analista)**,
preferindo **bases distintas** e priorizando relevância — em revisão **única** ou
**dupla** (§4.3). Não há triagem dupla mascarada, κ, checklist nem calibração — esses
painéis ficam ocultos.

Em ambos, os **incluídos viram `Artigo`**; no modo `anco` com sorteio, o analista vê
em **"A analisar"** apenas os **artigos atribuídos a ele**, de onde abre a **análise
pela Matriz AnCo** (§4.3).

O **cadastro avulso** por DOI/ISBN (lookup **Crossref**/cache 24h e **OpenLibrary**/
cache 30d, com reaproveitamento quando o identificador já existe) **continua existindo,
mas restrito a curador/admin** — é exceção, não o caminho do analista. Detalhe completo
dos dois modos, dos projetos e do rigor metodológico na **§8**.

### 4.3. Análise estruturada (4 abas)

1. **Identificação** — metadados (read-only) + **grande área** editável.
2. **Presença e pertinência** — perguntas Sim/Não (o termo "Análise Cognitiva"
   aparece no título/resumo/palavras-chave/referências/corpo; pertinência; define
   o conceito) + aspectos relevantes e definição extraída.
3. **Análise do artigo** — objeto, objetivo, foco, metodologia, **epistemologia**
   e **teoria** (multi-seleção com busca/tags), referenciais, resultados, contexto,
   observações.
4. **Resenha crítica (opcional)** — texto autoral, em página própria.

Auto-save a cada 30s. O botão **"Submeter para curadoria" só aparece quando todos
os campos das abas 1–3 estão preenchidos** (a aba 4 é opcional), com trava também
no servidor.

No modo `anco`, o sorteio define se cada artigo recebe **revisão única** (uma
análise → curadoria normal, §4.4) ou **dupla** (duas análises **independentes** de
analistas distintos → o **curador concilia** em `ConsensoAnalise`, registrando a
análise final; as duas de origem são preservadas como insumo). A constraint
`(artigo, analista)` continua valendo: a pluralidade interpretativa é a base da
revisão dupla.

### 4.4. Aprovação editorial por curadoria

Submetida, a análise entra na **fila de curadoria**
(`/acervo-analista/curadoria/`). Um **curador** pré-visualiza a análise e decide:
**Aprovar e publicar** (entra no acervo), **Pedir ajustes** (volta a rascunho, com
justificativa) ou **Rejeitar**. A publicação da análise é, portanto, por
**aprovação humana de curadoria** — não há revisão por pares da análise em si.

### 4.5. Revisão cega por pares da resenha crítica

A **resenha crítica** segue trilha independente: o autor a **submete à revisão
cega**; o sistema **sorteia 2 revisores** (excluindo o autor e coautores do mesmo
artigo, respeitando disponibilidade/carga); aprovação unânime leva a resenha a
**revisada**; a **curadoria confirma** e a resenha passa a **publicada** (visível
no acervo com selo). A análise pode estar pública enquanto a resenha ainda está em
revisão — os ciclos são independentes.

### 4.6. Acervo público e gestão

- **Acervo** (`/acervo/`): listagem facetada (base, status, área, resenha, acesso
  aberto), busca **textual** (FTS Postgres + `unaccent`) ou **semântica**; página
  do artigo, página da análise (com citações ABNT/APA e JSON-LD), **planilha**
  tabular e **estatísticas** do acervo (por ano, base, idioma).
- **Despublicar/Restaurar** (exclusão suave): curador/admin removem uma entrada do
  acervo público (status `despublicada`) **preservando-a no banco** para eventual
  restauração — direto na página da análise.

---

## 5. Aspectos metodológicos

- **Cadastro aberto + curadoria** desloca o controle de qualidade do *gate* de
  entrada (quem pode entrar) para o *gate* de publicação (curadoria aprova o que
  entra no acervo) — reduz atrito de adesão sem abrir mão do rigor.
- **Pluralidade preservada**: a constraint `(artigo, analista)` permite múltiplas
  análises do mesmo artigo por analistas distintos, registrando divergência como
  evidência.
- **Revisão por pares onde ela agrega valor**: a catalogação estrutural é validada
  por curadoria; a **revisão cega por pares** é reservada à **resenha crítica** —
  o juízo interpretativo autoral —, com mascaramento de autoria testado.
- **Prevenção de duplicidade** em três níveis (DOI → ISBN → hash determinístico) e
  **reaproveitamento** de artigo existente no cadastro.
- **Vocabulário controlado com sinônimos**: o formulário oferece só termos `ativo`;
  variantes legadas entram como `ativo=False` (visíveis à curadoria, ocultas no
  cadastro), impedindo a reintrodução de "Empirismo/empirismo/Empírica".
- **Integridade de acesso**: validação de link (HEAD→GET, guarda anti-SSRF),
  *snapshot* Wayback opcional e re-verificação periódica.

---

## 6. Busca semântica

Ver [apps/busca_semantica/](apps/busca_semantica/) e
[docs/relatorios/fase-8.md](docs/relatorios/fase-8.md).

- **Embeddings vetoriais** (`pgvector`, 384-dim) para Artigo (título+resumo+
  palavras-chave), Análise (campos estruturais) e Resenha (texto crítico isolado).
- **Serviço local** (FastAPI + sentence-transformers,
  `paraphrase-multilingual-MiniLM-L12-v2`) — sem API externa nem custo recorrente.
- **Geração assíncrona** via signals + django-q2 (retry/backoff; falha não bloqueia
  publicação). Comando `reindexar_embeddings` popula o acervo.
- **Toggle explícito** na busca (`?modo=textual` × `?modo=semantico`) — sem
  hibridização opaca; indicador de similaridade 0–100% por resultado; degradação
  graciosa para textual se o serviço estiver offline.
- **Limites deliberados** (ESPECIFICAÇÃO §6.2.1): embeddings são **acesso à
  informação**, não produção de análise — não pré-preenchem campos, não detectam
  pertinência, não sugerem revisores nem geram resenhas.

---

## 7. Stack tecnológica — vantagens, desvantagens e substitutos

Arquitetura em **5 serviços** Docker Compose: `web` (Django+Gunicorn), `worker`
(django-q2), `db` (Postgres+pgvector), `cache` (Redis), `embeddings`
(FastAPI+sentence-transformers; opcional). Em produção, `caddy` termina TLS e serve
estáticos. **Frontend deliberadamente leve** (server-rendered + HTMX/Alpine, sem
SPA): URL estável e citável desde o primeiro carregamento; servidor como fonte
única da verdade.

| Componente | Papel | Vantagens | Desvantagens | Substitutos possíveis |
|---|---|---|---|---|
| **Django 5** (Python 3.12) | Framework web, ORM, admin | Maturidade, ORM robusto, admin pronto, ecossistema rico, segurança por padrão | Monolito; menos "moderno" que stacks JS; ORM pode esconder custos de query | FastAPI+SQLModel, Rails, Laravel, Node/NestJS |
| **PostgreSQL 16 + pgvector** | Banco relacional + busca vetorial | ACID, FTS nativo com `unaccent`, **vetores no mesmo banco** (sem store dedicado), JSON/Array | Busca vetorial menos escalável que bancos vetoriais dedicados em escala muito grande | MySQL (sem vetor nativo), SQLite (dev), bancos vetoriais (Qdrant, Weaviate, Milvus) |
| **Redis 7** | Broker da fila + cache | Simples, rápido, padrão de mercado | Mais um serviço; persistência exige configuração | Postgres como broker (django-q2 ORM), RabbitMQ, Valkey |
| **django-q2** | Tasks assíncronas (sorteio, e-mail, embeddings, cron) | Integrado ao Django/ORM, simples de operar, agendamento embutido | Menos recursos que Celery; comunidade menor | Celery (+Redis/RabbitMQ), Dramatiq, RQ |
| **django-allauth + Google OAuth** | Autenticação | Login social pronto, seguro, vinculação por e-mail | Configuração de credenciais OAuth; acoplamento ao provedor | Authelia/Keycloak (SSO), python-social-auth, auth próprio |
| **django-simple-history** | Auditoria/versionamento | Histórico por linha transparente, integra ao admin | Cresce o banco; overhead de escrita | django-reversion, triggers/temporal tables no Postgres |
| **sentence-transformers (MiniLM multilíngue)** | Embeddings locais | Sem custo/recorrência, sem dependência externa, multilíngue (PT) | Qualidade inferior a modelos grandes/pagos; precisa de CPU/RAM | OpenAI/Cohere embeddings (API paga), modelos BGE/E5, Instructor |
| **HTMX + Alpine.js + Tailwind** | Frontend leve | Sem build SPA, URLs citáveis, baixa complexidade, progressive enhancement | Interatividade rica é mais trabalhosa; Alpine depende de JS no cliente | React/Vue (SPA), Hotwire/Turbo, Livewire-like |
| **Tom Select / Tabulator** (CDN) | Multi-seleção com busca / grade tabular | Resolve UX de listas grandes (epistemologia/teoria) e planilha, sem framework | Dependência de CDN externo (CSP); JS no cliente | Select2, Choices.js; AG-Grid, DataTables |
| **django-unfold** | Tema do admin | Admin moderno para curadoria, baixo esforço | Dependência extra; customização limitada ao framework | admin padrão do Django, Django-Jazzmin, painel próprio |
| **Caddy 2** | Reverse proxy + TLS | TLS automático (Let's Encrypt), config mínima | Menos difundido que Nginx em alguns ambientes | Nginx + Certbot, Traefik |
| **Docker Compose** | Orquestração local/prod simples | Reprodutível, baixo atrito, 1 comando | Não é orquestração de cluster; escala horizontal limitada | Kubernetes, Nomad, Docker Swarm |
| **pytest + ruff** | Testes e lint/format | Rápido, expressivo; ruff unifica lint+format | — | unittest, flake8+black+isort |

**Trade-off central**: a stack privilegia **simplicidade operacional, baixo custo e
reprodutibilidade** (tudo self-hosted, um `docker compose`, sem APIs pagas) sobre
escalabilidade massiva e UX de SPA — coerente com um acervo de pesquisa de porte
pequeno/médio mantido por um grupo acadêmico. Os principais pontos de atenção
(desvantagens assumidas) são: (i) busca vetorial em Postgres não escala como um
banco vetorial dedicado; (ii) embeddings locais têm teto de qualidade; (iii)
dependência de Alpine/CDN no cliente; (iv) Compose não cobre alta disponibilidade.

---

## 8. Dois modos por projeto: Triagem PRISMA-ScR (rigoroso) e Revisão ANCO (simplificado)

A seleção de fontes **anterior à análise** vive no app nativo **aditivo**
(`apps/triagem`), sem alterar o schema do acervo: candidatos vivem em tabelas
próprias e **só os incluídos viram `Artigo`**. Cada **projeto** escolhe **um de dois
modos** (`ProtocoloTriagem.modo`, default `rigoroso`) — um **toggle por projeto**,
**aditivo e reversível**, em que **nenhum dos fluxos remove o outro**:

- **`rigoroso` — Triagem PRISMA-ScR (Fases 9–12):** triagem por **≥2 revisores
  independentes** com mascaramento, consenso/desempate, concordância e protocolo a
  priori — tornando a seleção **equivalente ao PRISMA-ScR** (*PRISMA extension for
  Scoping Reviews*). Detalhado em §8.1.
- **`anco` — Revisão ANCO (Fase 13):** fluxo **simplificado** que reproduz a prática
  da disciplina de Análise Cognitiva — autotriagem pelo dono da base, lista por
  relevância e sorteio de cota para análise (única/dupla). Detalhado em §8.2.

Em ambos, a **importação** (RIS/BibTeX/CSV) e a **dedup** (DOI > ISBN > hash +
`pg_trgm`, com auditoria, procedência e reversão) são idênticas, e o **acervo
histórico (legado)** — base de fundação curada por Eneida Santana — **não passa por
triagem nem é editável por analistas**, por construção.

### 8.1. Modo `rigoroso` — Triagem PRISMA-ScR

**Projetos (Fase 12).** Cada **projeto** é uma revisão de escopo independente —
pergunta, estratégia de busca, protocolo registrado, corpus, fluxograma e
concordância próprios. O admin designa a **equipe** (membros com papel
analista/curador *por projeto*). Rotas escopadas por URL: `/triagem/` lista os
projetos do usuário e `/triagem/p/<slug>/` é a home do projeto. Acervo, análise,
usuários e vocabulário permanecem **globais** (o mesmo artigo pode ser incluído por
mais de um projeto, com uma única análise).

Fluxo de cada projeto:

1. **Importação por arquivo** (**RIS/BibTeX/CSV**) com **dedup** determinística
   (DOI > ISBN > hash) + revisão de **possíveis duplicatas** por similaridade de título
   (`pg_trgm`), com **auditoria** (quem/quando), **procedência** (base + importador) e
   **reversão**. Quem já casa com o acervo (inclusive o legado) é marcado e **não** é triado.
2. **Triagem dupla, mascarada** — cada registro vai a **≥2 revisores membros**, que
   decidem **incluir/excluir/dúvida** (com motivo), cegos ao coletor e aos pares.
   Opcional **por projeto**: **2 etapas** (título/resumo → texto completo).
3. **Consenso → incluído/excluído**; **divergência → desempate** por curador.
4. **Promoção** dos incluídos a `Artigo` (idempotente) → **análise pela Matriz AnCo**.
5. **Rigor metodológico (Fase 11):** **concordância κ de Fleiss** + % de acordo,
   **checklist PRISMA-ScR** (22 itens), **protocolo a priori** versionado/travado com
   **registro externo** (OSF) e **calibração (piloto)** com gate de κ. **Fluxograma
   PRISMA-ScR** em `/triagem/p/<slug>/prisma/`, com export **CSV/JSON**.

**Permissões.** Acesso e ações exigem ser **membro** do projeto; o **curador** gerencia
tudo (e o admin é curador de qualquer projeto). O **analista** resolve apenas duplicatas
de bases que **ele importou** e exclui apenas as **próprias** importações; a autorização
é no servidor (não só na UI). O **acervo histórico (legado)** — base de fundação curada
por Eneida Santana — **não passa por triagem nem é editável por analistas**, por construção.

Com isso, no modo rigoroso o acervo é não só uma base navegável, mas um **protocolo de
revisão de escopo reprodutível e reportável** de ponta a ponta. Detalhes em
[docs/relatorios/fase-9.md](docs/relatorios/fase-9.md) … [fase-12.md](docs/relatorios/fase-12.md)
e em [docs/planos/fase-12-projetos.md](docs/planos/fase-12-projetos.md).

### 8.2. Modo `anco` — Revisão ANCO (simplificado)

Para grupos que seguem a prática da **disciplina de Análise Cognitiva** (Profas.
Teresinha Fróes e Leliana), o modo `anco` automatiza um fluxo mais leve, **sem o
aparato PRISMA-ScR** — meta de UX: o analista vê **pouco, ordenado e com cota fixa**,
não a pilha inteira. Tudo vive atrás do `modo` do projeto; o código rigoroso
permanece intacto.

1. **Importação + dedup** idênticas ao modo rigoroso (acima).
2. **Autotriagem:** o **dono da base tria os próprios registros** (incluir/excluir,
   **revisor único**; sem "dúvida", para não gerar desempate), reusando a
   consolidação e a promoção ao acervo. Gate de propriedade espelha a dedup
   (`importadores`); curador/admin podem agir sobre qualquer base.
3. **Relevância por termos (sem embeddings):** `relevancia_score` = nº de termos
   distintos da estratégia de busca presentes em título/resumo/palavras-chave. A
   tela de **incluídos** (`/triagem/p/<slug>/incluidos/`) ordena por relevância, com
   badge explicável ("casou com N termos"). Comando `recalcular_relevancia`.
4. **Sorteio de análise** (`/triagem/p/<slug>/sorteio-analise/`): o curador escolhe
   **única** ou **dupla** e a **cota (5/analista)**; o algoritmo guloso distribui
   priorizando relevância e **preferindo bases distintas** (preferência, **nunca**
   bloqueia a cota), sem reatribuir o que o analista já analisou. **Idempotente**;
   **faltas são logadas** (pool insuficiente) — sem truncamento silencioso.
5. **Análise pela Matriz AnCo:** em **"A analisar"** o analista vê **só os artigos
   atribuídos** a ele. **Única** → curadoria normal; **dupla** → 2 análises
   independentes → o curador **concilia** em `ConsensoAnalise`
   (`/triagem/p/<slug>/consenso/`), registrando a análise final.

Detalhes em [docs/relatorios/fase-13.md](docs/relatorios/fase-13.md) e
[docs/planos/fase-13-revisao-anco.md](docs/planos/fase-13-revisao-anco.md).

Demais frentes de roadmap: relevância **semântica** por embeddings/base referencial no
modo ANCO; comparação lado a lado na tela de consenso; calibração ativa da busca
semântica; edição da estratégia de busca direto na página do protocolo; fusão de contas
de analistas legado.

---

## 9. Bootstrap local e comandos

Pré-requisitos: **Docker 24+**, **Docker Compose v2+**, **Git**.

```bash
cp .env.example .env          # gere DJANGO_SECRET_KEY: python -c "import secrets;print(secrets.token_urlsafe(50))"
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml exec web python manage.py migrate
docker compose -f infra/docker-compose.yml exec web python manage.py loaddata vocabularios_iniciais
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser
# App: http://localhost:8000/  · Admin: /admin/  · Health: /healthz
docker compose -f infra/docker-compose.yml --profile embeddings up -d   # busca semântica (opcional)
```

```bash
# Testes / qualidade
docker compose -f infra/docker-compose.yml exec web pytest --cov
docker compose -f infra/docker-compose.yml exec web ruff check . && ruff format .
# Carga do acervo de fundação — base revisada e curada (idempotente)
docker compose -f infra/docker-compose.yml exec web python manage.py migrate_base_revisada [--dry-run]
# Embeddings
docker compose -f infra/docker-compose.yml exec web python manage.py reindexar_embeddings [--tudo]
# Recarga sem rebuild (só template/view): kill -s HUP no gunicorn
docker compose -f infra/docker-compose.yml kill -s HUP web
```

Convenções de desenvolvimento em [CLAUDE.md](CLAUDE.md).

---

## 10. Como citar, autoria e licença

```bibtex
@inproceedings{santos_anco_2026,
  author    = {Santos, Paulo Vicente Moreira dos and Santana, Eneida and {Grupo de Pesquisa do PPGDC}},
  title     = {De planilha a plataforma: catalogação colaborativa, curadoria
               editorial e revisão por pares para análise cognitiva da
               literatura científica},
  booktitle = {Anais do Congresso de Difusão do Conhecimento},
  year      = {2026},
  note      = {No prelo}
}

@software{anco_plataforma_2026,
  author  = {Santos, Paulo Vicente Moreira dos and Santana, Eneida and {Grupo de Pesquisa do PPGDC}},
  title   = {{AnCo} --- Plataforma de Análise Cognitiva},
  year    = {2026},
  url     = {https://github.com/mestrepv/anco-ufba},
  license = {AGPL-3.0-or-later (código); CC BY-NC 4.0 (conteúdo)}
}
```

Cada análise publicada tem **URL estável** e citações **ABNT 6023:2018** e **APA 7ª
ed.** geradas automaticamente ([apps/publico/services.py](apps/publico/services.py)).

**Autoria e equipe**

- **Paulo Vicente Moreira dos Santos** (nome de citação: **SANTOS, P. V. M. dos**) ·
  <paulovicente.ifba@gmail.com> — concepção e desenvolvimento da plataforma.
- **Eneida Santana** — bibliotecária e **Doutora em Difusão do Conhecimento**;
  equipe fundadora. Responsável pela **curadoria bibliográfica do acervo de
  fundação** (`base-anco-revisada.json`). Pesquisadora
  de formação docente, tecnologias educacionais e práticas extensionistas; membra
  do Grupo de Pesquisa **TICASE** (Tecnologia da Informação e Comunicação
  Aplicadas à Educação e Saúde). Especialista em Educação a Distância: Tecnologias
  Educacionais (IFPR, 2016); Mestre em Ciência da Informação (UFBA, 2011);
  Bacharel em Biblioteconomia e Documentação (UFBA, 2008).
- **Grupo de pesquisa do PPGDC** — linha, orientação e demais pesquisadores
  (a preencher antes da submissão).

**Licenciamento** — este repositório é licenciado em duas partes:

| O quê | Licença | Arquivo |
|---|---|---|
| Código-fonte | **AGPL-3.0-or-later** | [LICENSE](LICENSE) |
| Conteúdo (documentação, análises, resenhas, dataset) | **CC BY-NC 4.0** | [LICENSE-CONTENT](LICENSE-CONTENT) |

A AGPL é deliberada: quem rodar uma instância modificada desta plataforma como
serviço em rede deve disponibilizar o código correspondente. Vale para a
plataforma de pesquisa pública que ela é.

**Obras referenciadas** ficam de fora de ambas: a plataforma cataloga metadados
e link, **nunca hospeda a obra** — os direitos permanecem com os detentores.

**Metadados de citação** — [CITATION.cff](CITATION.cff) alimenta o botão *Cite
this repository* do GitHub; [.zenodo.json](.zenodo.json) alimenta os metadados
do depósito no Zenodo. Ao mudar autoria, versão ou licença, atualize os dois
junto com as entradas BibTeX acima — são quatro lugares que precisam concordar.
