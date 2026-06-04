# Relatório — Fase 9: Triagem PRISMA-ScR (em andamento)

Etapa de **seleção de fontes** anterior à análise (upstream da Matriz AnCo),
reprodutível e reportável segundo o **PRISMA-ScR**. App nativo `apps/triagem`,
**aditivo** (tabelas novas; sem alterar o schema de `acervo`).

> Entrega **faseada** (CLAUDE.md §2): uma sub-fase por vez, com parada para
> aprovação humana. Este relatório é atualizado ao fim de cada sub-fase.

## Decisões de produto (confirmadas com o usuário)

- **App nativo** no AnCo (não importador da ferramenta RSL/Streamlit).
- **Ingestão por arquivos** (RIS/BibTeX/CSV exportados de cada base).
- **Tabela separada** para candidatos; **só os INCLUÍDOS viram `Artigo`**.
- **Uma revisão de escopo única** (protocolo AnCo, singleton).
- **Legado isento:** o acervo histórico (`status = legado`) não passa por triagem.

## Plano de sub-fases

| Sub-fase | Escopo | Status |
|---|---|---|
| **9.0** | Scaffolding: app vazio, INSTALLED_APPS, include de URL, painel placeholder, spec addendum | ✅ concluída |
| **9.1** | Models (ProtocoloTriagem, Busca, RegistroTriagem, DecisaoTriagem) + admin + migrations + seed | ✅ concluída |
| **9.2** | Importação RIS/BibTeX/CSV + dedup (intra-protocolo e vs. acervo) + command + upload view | ✅ concluída |
| **9.3** | Sorteio + avaliação + signals + tasks (≥2 revisores, consenso/divergência, prazos) | ⏳ pendente |
| **9.4** | UI de triagem mascarada + minhas-triagens + desempate do curador | ⏳ pendente |
| **9.5** | Promoção de incluídos → `Artigo` (idempotente; legado intocado) | ⏳ pendente |
| **9.6** | Contagens/diagrama PRISMA-ScR + proveniência | ⏳ pendente |

---

## Sub-fase 9.0 — Scaffolding (concluída)

### O que foi entregue
- App `apps/triagem` criado (`apps.py` com `TriagemConfig`, `ready()` que carrega
  `signals` de forma tolerante — entra na 9.3).
- Registrado em `INSTALLED_APPS` (`config/settings/base.py`), entre `acervo` e `publico`.
- URL montada em `/triagem/` (`config/urls.py`).
- Painel placeholder `triagem_painel` (`views.painel_view` + `templates/triagem/painel.html`),
  gated a analistas/curadores (reusa `User.eh_analista`).
- Addendum da Fase 9 em `docs/ESPECIFICACAO.md`.
- Testes de wiring/acesso (`apps/triagem/tests/test_scaffolding.py`): anônimo→302,
  leitor→403, analista→200.

### Critério de aceite
- [x] App carrega: `manage.py check` sem issues.
- [x] Sem migrações pendentes (`makemigrations --check` → "No changes detected").
- [x] `/triagem/` resolve e exige analista (testes verdes).
- [x] `ruff check apps/triagem/` limpo.

### Decisões tomadas
- Painel placeholder em vez de include de URL vazio — confirma o wiring de ponta a
  ponta (reverse + redirect de login + 403/200) sem mexer em comportamento existente.
- `ready()` usa `contextlib.suppress(ImportError)` para tolerar a ausência de
  `signals.py` até a 9.3.

### Desvios da especificação
- Nenhum. O addendum **estende** a especificação; o fluxo de `Analise` segue intacto.

### Dívida técnica deixada
- Nenhuma nesta sub-fase (puro scaffolding).

### Métricas
- Arquivos novos: app `apps/triagem/*` + 1 template + 1 teste.
- Cobertura: 3 testes (acesso ao painel).

### Pendências para o usuário
- Aprovar para iniciar a **9.1** (models + migrations aditivas + seed do protocolo).

---

## Sub-fase 9.1 — Models + migrations + admin + seed (concluída)

### O que foi entregue
- **4 modelos** (`apps/triagem/models.py`):
  - `ProtocoloTriagem` (singleton; critérios de inclusão/exclusão, `n_revisores`
    default 2, `prazo_dias` default 21; `classmethod ativo()`).
  - `Busca` (por base; reusa o vocabulário `base` via `base_consulta` +
    `outra_base`; `n_identificados`, `arquivo`, `formato` RIS/BibTeX/CSV).
  - `RegistroTriagem` (candidato pré-`Artigo`; campos bibliográficos; `identificador`
    determinístico de dedup; `status` IDENTIFICADO/EM_TRIAGEM/INCLUIDO/EXCLUIDO/DUPLICADO;
    `motivo_exclusao`, `duplicado_de`, `ja_no_acervo`, `artigo` FK proveniência,
    `decisao_final`/`decidida_por/em`; `HistoricalRecords`).
  - `DecisaoTriagem` (parecer de 1 revisor; análogo a `Revisao`; `UniqueConstraint(registro, revisor)`).
- **Helper `chave_dedup()`** reusa `acervo.models._gerar_identificador_interno` →
  DOI normalizado > ISBN > hash(título|ano|periódico). Idêntico ao `Artigo`.
- **Admin Unfold** dos 4 modelos (`apps/triagem/admin.py`) com inline de decisões
  no registro e `SimpleHistoryAdmin` para auditoria.
- **Migrations:** `0001_initial` (4 modelos + Historical + 2 UniqueConstraints),
  `0002_seed_protocolo` (cria o protocolo singleton, idempotente).

### Critério de aceite
- [x] `makemigrations --check` → "No changes detected" (models ↔ migrations em sincronia).
- [x] `migrate` aplica limpo; seed cria 1 protocolo (n_revisores=2, prazo=21).
- [x] `ruff check apps/triagem/` limpo; `manage.py check` sem issues (admin ok).
- [x] **Aditivo**: nenhuma migração tocou `acervo`/`core`.
- [x] Testes (`test_models.py`, 11): dedup (DOI/ISBN/hash), unicidade por
      `(protocolo, identificador)`, mesma chave em protocolos distintos OK, M2M
      `origem_buscas`, singleton `ativo()`, unicidade `(registro, revisor)`.
- [x] Suíte completa: **365 passed, 1 xpassed**.

### Decisões tomadas
- `identificador` é a chave de dedup *intra-protocolo* (não global) — `UniqueConstraint(protocolo, identificador)` permite a mesma referência em revisões distintas.
- `idioma` em `RegistroTriagem` é `CharField` livre (dados de import variam); mapeado para `Artigo.Idioma` só na promoção (9.5).
- Proveniência mora em `RegistroTriagem.artigo` (triagem→acervo); `Artigo` **não** foi tocado.
- `simple-history` só em `RegistroTriagem` (decisões de triagem são auditáveis via histórico do registro + `DecisaoTriagem`).

### Desvios da especificação
- Nenhum. Estende o addendum da Fase 9.

### Dívida técnica deixada
- Concordância/kappa entre revisores: derivável das `DecisaoTriagem` (não bloqueia; futura).

### Pendências para o usuário
- Aprovar para a **9.2** (importação RIS/BibTeX/CSV + dedup + command + upload view) —
  introduz as dependências `rispy`/`bibtexparser` (rebuild de `web`/`worker`).

---

## Sub-fase 9.2 — Importação + deduplicação (concluída)

### O que foi entregue
- **Parsers** (`apps/triagem/importacao.py`): `parse_ris` (rispy), `parse_bibtex`
  (bibtexparser v1), `parse_csv` (stdlib, detecta delimitador e mapeia cabeçalhos
  flexíveis) → dicts normalizados (título, autores, ano, doi, isbn, resumo,
  palavras-chave, periódico, idioma, link). `decodificar()` (utf-8/latin-1) e
  `detectar_formato()` pela extensão.
- **Dedup** (`importar_para_busca`): chave determinística (`chave_dedup`); mesma
  referência vinda de várias bases → mesclada via `origem_buscas` (conta como
  duplicado, não cria linha). Contra o acervo: casa com `Artigo` existente
  (inclusive **legado**) → `ja_no_acervo=True`, vincula `artigo`, **não re-tria**.
  Idempotente.
- **Management command** `importar_triagem <arquivo> --base <nome> [...]` (cria a
  `Busca` e importa; idempotente).
- **Upload view** `/triagem/importar/` (`ImportarBuscaForm`) + **painel** com
  contagens por status e buscas recentes + **lista de registros** `/triagem/registros/`
  (facetas por status), gated a analistas/curadores. Guarda o arquivo cru em
  `Busca.arquivo` para auditoria.
- **Dependências:** `rispy>=0.9`, `bibtexparser>=1.4,<2` em `pyproject.toml`
  (rebuild de `web`/`worker`).

### Critério de aceite
- [x] Parsers mapeiam RIS/BibTeX/CSV (3 testes).
- [x] Dedup intra-protocolo mescla origens; reimport idempotente; sem-título ignorado.
- [x] Candidato que casa com `Artigo` (legado) vira `ja_no_acervo`, não novo.
- [x] Upload: leitor 403; analista importa RIS e cria registro (redirect p/ lista).
- [x] `ruff` limpo; telas `/triagem/{,importar/,registros/}` renderizam 200.
- [x] Suíte completa: **374 passed, 1 xpassed**.

### Decisões tomadas
- `ja_no_acervo` mantém `status=identificado` + flag (não cria status terminal); o
  sorteio (9.3) excluirá esses do rastreio. Mantém o registro visível/contável.
- bibtexparser fixado em v1 (API estável `loads().entries`); v2 muda a API.
- Lista de registros adiantada para a 9.2 (validação do import); a interface de
  triagem por revisor e o desempate seguem na 9.4.

### Dívida técnica deixada
- Parsers cobrem o caminho comum; campos exóticos de bases específicas podem exigir
  ajuste de mapeamento (arquivo cru fica guardado p/ reprocessar).

### Pendências para o usuário
- Aprovar para a **9.3** (sorteio de ≥2 revisores + avaliação consenso/divergência +
  signals + tasks assíncronas; usa o `worker`).
