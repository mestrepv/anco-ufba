# Roadmap — UX do analista + lookup Crossref

**Branch**: `feat/analista-ux-crossref` (a partir de `main`)
**Objetivo**: que um analista cadastrado entre na área autenticada,
digite um identificador (DOI ou ISBN) e veja os metadados preenchidos
automaticamente, confirme e siga para a análise — com visual coerente
ao resto do site.

**Mockup validado**: `https://anco.paulovicente.pro.br/static/mockups/cadastro-artigo.html`

---

## Convenções

- **Cada marco fecha em um commit ou pequeno grupo de commits atômicos**
  (Conventional Commits, em pt-BR).
- **Cobertura mínima**: 70% nas linhas novas (CLAUDE.md §6). Rodar
  `pytest --cov=apps/acervo` antes de marcar o marco como ✅.
- **Cada marco precisa passar `ruff check`, `ruff format`, `pytest`**
  antes de virar commit.
- **Não pular marcos**: a ordem é M1 → M7. Frontend depende de
  backend; tests depende dos dois.
- **Tamanho**: P (≤2 h), M (≤6 h), G (≤1 dia).

---

## M0 — Setup ⏱ P

- [ ] Criar branch `feat/analista-ux-crossref` a partir de `main` atualizado
- [ ] Confirmar `docker compose up -d` sobe (web + db + cache + worker)
- [ ] `pytest` passa no main antes de começar (baseline limpo)

**Aceite**: branch existe; `pytest` verde; container web responde em `127.0.0.1:9090`.

---

## M1 — Serviço de lookup DOI (Crossref) ⏱ M

Refatorar o lookup de DOI que hoje vive em `apps/core/views.py` para
um serviço próprio do app `acervo`, com cache. **Uma API só**:
Crossref. Cobre o caso comum (DOI tem metadados completos lá em
~95% dos casos, abstract em ~30–50%). O que não vier — abstract
ausente, palavra-chave faltando, etc. — fica como campo vazio para
o analista preencher manualmente na tela.

- [ ] Criar `apps/acervo/services/__init__.py` (transformar em pacote)
- [ ] Mover `services.py` atual para `apps/acervo/services/links.py` (validar_link, snapshot_wayback)
- [ ] Criar `apps/acervo/services/_base.py` com dataclass `LookupResultado` (encontrado, erro, dados) — compartilhada com o serviço ISBN do M2
- [ ] Criar `apps/acervo/services/crossref.py` com:
  - [ ] função `normalizar_doi(raw) -> str` (strip de `https://doi.org/`, `doi:`, etc.)
  - [ ] função `lookup_doi(doi) -> LookupResultado`:
    - [ ] bate em `https://api.crossref.org/works/<doi>?mailto=<EMAIL>`
    - [ ] limpa abstract de tags JATS (`<jats:p>` etc.) quando presente
    - [ ] retorna `encontrado=False` em HTTP 404
    - [ ] retorna `encontrado=False, erro="..."` em outros erros (timeout, rede)
    - [ ] mapeia campos pro formato consumido pelo template (titulo, autores, autores_str, periódico, ano, volume, número, paginas, ISSN, editora, tipo, resumo, palavras_chave, url, licenca, citacoes_crossref)
  - [ ] cache via `django.core.cache` com chave `lookup:doi:<doi>` (TTL 24h)
  - [ ] timeout 5s, captura `URLError`, `HTTPError`, `socket.timeout`
  - [ ] User-Agent identificável: `AnCo/1.0 (mailto:paulovicente.ifba@gmail.com)`
- [ ] Atualizar `apps/core/views.py:consultar_doi_view` para usar o novo serviço (a chamada existente para Semantic Scholar é descontinuada — simplifica o código)
- [ ] Tests `apps/acervo/tests/test_crossref_service.py`:
  - [ ] DOI bem-formado mockado retorna `LookupResultado.encontrado=True` com campos preenchidos
  - [ ] HTTP 404 → `LookupResultado.encontrado=False`
  - [ ] Timeout simulado → `LookupResultado.encontrado=False, erro="timeout"`
  - [ ] DOI com prefixo URL é normalizado
  - [ ] Abstract com tags JATS é limpo
  - [ ] Segunda chamada com mesmo DOI usa cache (mock é chamado 1×)

**Aceite**: ferramenta `/ferramentas/doi/` continua funcionando; novo serviço chamável de qualquer view do app acervo; cobertura ≥80% no `crossref.py`.

**Commit**: `refactor(acervo): extrai lookup Crossref para services com cache`

---

## M2 — Serviço de lookup ISBN (OpenLibrary) ⏱ M

Mesmo padrão do M1, mas para livros e capítulos. **Uma API só**:
OpenLibrary. Cobre a maioria dos livros acadêmicos catalogados em
inglês e parte dos brasileiros. ISBN não encontrado → analista
preenche manualmente.

- [ ] Criar `apps/acervo/services/isbn.py` com:
  - [ ] função `validar_isbn(raw) -> str | None`:
    - [ ] strip de hífens e espaços
    - [ ] checksum ISBN-10 (módulo 11) e ISBN-13 (módulo 10)
    - [ ] retorna ISBN normalizado (sem hífens) ou None
  - [ ] função `lookup_isbn(isbn) -> LookupResultado`:
    - [ ] bate em `https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&format=json&jscmd=data`
    - [ ] retorna `encontrado=False` quando o JSON volta vazio (`{}`)
    - [ ] cache via `django.core.cache` chave `lookup:isbn:<isbn>` (TTL 30 dias — livros mudam menos)
    - [ ] timeout 5s
  - [ ] mapeia campos pro mesmo formato do `crossref.LookupResultado.dados`:
    - `titulo`, `autores` (lista), `autores_str`
    - `editora` (publishers[0])
    - `ano` (publish_date)
    - `paginas` (number_of_pages, se disponível)
    - `isbn`, `isbn_13`, `isbn_10`
    - `resumo` (description ou notes, se houver)
    - `palavras_chave` (subjects, primeiros 10)
    - `tipo` = "Livro" (sem heurística complexa — capítulos são raros via ISBN)
    - `url` (preview link OpenLibrary)
    - `cover` (URL da imagem grande, se houver)
- [ ] Tests `apps/acervo/tests/test_isbn_service.py`:
  - [ ] `validar_isbn`: ISBN-10 válido (`0306406152`), inválido, ISBN-13 válido (`9780128038031`), com hífens, com espaços
  - [ ] `lookup_isbn` mockando OpenLibrary com hit → retorna dados normalizados
  - [ ] `lookup_isbn` OpenLibrary sem hit → `LookupResultado.encontrado=False`
  - [ ] timeout simulado → `LookupResultado.encontrado=False, erro="timeout"`
  - [ ] segunda chamada usa cache (mock só é chamado 1×)

**Aceite**: serviço testado isoladamente; cobertura ≥80% no `isbn.py`; não introduz dependência externa (apenas `urllib`).

**Commit**: `feat(acervo): adiciona lookup ISBN via OpenLibrary`

---

## M3 — Model permite Artigo sem DOI ⏱ M

Hoje `Artigo.doi` é obrigatório e único. Precisa aceitar livros (ISBN)
e artigos sem identificador externo.

- [ ] Em `apps/acervo/models.py:Artigo`:
  - [ ] `doi`: trocar para `null=True, blank=True, unique=True` (PostgreSQL aceita múltiplos NULLs em unique)
  - [ ] Adicionar `isbn` (CharField max_length=17, opcional, validador básico de 10 ou 13 dígitos sem hífens)
  - [ ] Adicionar `tipo_publicacao` (CharField com choices: ARTIGO/CAPITULO/LIVRO/DISSERTACAO/TESE/OUTRO)
  - [ ] Adicionar `identificador_interno` (CharField, unique, formato `legacy:HASH16`)
  - [ ] Override `save()`: se `doi`, `isbn` vazios e `identificador_interno` vazio → gerar `legacy:` + sha1(titulo|ano|periodico)[:16]
  - [ ] Property `identificador_canonico` retornando primeiro de: doi → isbn → identificador_interno
- [ ] Migration `apps/acervo/migrations/00XX_artigo_sem_doi.py`:
  - [ ] AlterField `doi` (null=True)
  - [ ] AddField `isbn`, `tipo_publicacao`, `identificador_interno`
  - [ ] RunPython forward: para registros existentes, popular `identificador_interno` quando precisar (idempotente)
  - [ ] reverse_code seguro
- [ ] Atualizar `Artigo.__str__` para usar `identificador_canonico`
- [ ] Tests `apps/acervo/tests/test_artigo_sem_doi.py`:
  - [ ] Cria Artigo sem DOI/ISBN → ganha `identificador_interno` determinístico
  - [ ] Mesmo título/ano/periódico → mesmo hash (idempotência)
  - [ ] Migration roda sem erro num banco com 1.443 registros simulados (factory)

**Aceite**: `python manage.py migrate` aplica e reverte sem erro; admin mostra novos campos; tests passam.

**Commit**: `feat(acervo): permite Artigo sem DOI (ISBN ou identificador interno)`

---

## M4 — Forms divididos e validação ⏱ M

Hoje `ArtigoForm` exige DOI. Preciso de um form de **lookup** (input
único) e um form de **metadados** (campos editáveis com DOI opcional).

- [ ] Em `apps/acervo/forms.py`:
  - [ ] Criar `IdentificadorLookupForm`:
    - [ ] campo único `identificador` (CharField max 200)
    - [ ] `clean_identificador()`: normaliza, detecta tipo (`doi`/`isbn`/`url`/`desconhecido`), retorna dict `{tipo, valor}`
    - [ ] usa `services.crossref.normalizar_doi()` e `services.isbn.validar_isbn()` para detectar formato
  - [ ] Criar `ArtigoMetadadosForm` substituindo `ArtigoForm`:
    - [ ] inclui `doi`, `isbn`, `tipo_publicacao` + todos os campos atuais
    - [ ] `doi.required = False`
    - [ ] `isbn.required = False`
    - [ ] `clean()`: exige (`doi` OU `isbn` OU (`titulo` E `ano` E `link_acesso`))
    - [ ] `clean_isbn()`: passa por `validar_isbn()` e rejeita se checksum inválido
  - [ ] Manter `ArtigoForm` como alias temporário de `ArtigoMetadadosForm` para não quebrar imports (deprecation comment)
- [ ] Tests `apps/acervo/tests/test_forms_artigo.py`:
  - [ ] form válido só com DOI
  - [ ] form válido só com ISBN-13
  - [ ] form válido só com ISBN-10
  - [ ] form rejeita ISBN com checksum inválido
  - [ ] form válido com fallback manual (título+ano+link)
  - [ ] form inválido vazio
  - [ ] `IdentificadorLookupForm` detecta DOI vs ISBN-10 vs ISBN-13 vs URL doi.org

**Aceite**: nenhum import quebrado em outros módulos; tests passam.

**Commit**: `feat(acervo): divide ArtigoForm em lookup + metadados`

---

## M5 — View HTMX de lookup + reescrita do cadastrar_artigo ⏱ G

Conectar lookup ao usuário via HTMX, e reescrever a view de cadastro
para fluxo lookup → preview → confirma.

- [ ] Em `apps/acervo/views.py`:
  - [ ] Adicionar `lookup_identificador_view` (GET):
    - [ ] decorator `_exige_analista`
    - [ ] aceita `?id=<doi-ou-isbn>` (parâmetro opcional `?tipo=doi|isbn` para forçar quando ambíguo)
    - [ ] valida via `IdentificadorLookupForm`
    - [ ] roteia: `tipo == "doi"` → `services.crossref.lookup_doi()`; `tipo == "isbn"` → `services.isbn.lookup_isbn()`
    - [ ] verifica se já existe `Artigo` com esse identificador (em `doi` OU `isbn`) → flag `ja_no_acervo`
    - [ ] renderiza `acervo/_preview_metadados.html` (parcial HTMX) com contexto unificado (`tipo`, `dados`, `encontrado`, `ja_no_acervo`)
  - [ ] Reescrever `cadastrar_artigo_view`:
    - [ ] GET inicial: render `cadastrar_artigo.html` com `IdentificadorLookupForm` vazio
    - [ ] POST: valida `ArtigoMetadadosForm`, cria Artigo, cria Analise rascunho, redireciona para edição
    - [ ] dados do lookup vêm em campos hidden no form (não em sessão — mais simples e idempotente)
- [ ] Em `apps/acervo/urls.py`: adicionar `path("artigo/lookup/", views.lookup_identificador_view, name="lookup_identificador")`
- [ ] Tests `apps/acervo/tests/test_lookup_view.py`:
  - [ ] GET com DOI válido + HTMX header → 200, contém título do artigo no HTML
  - [ ] GET com ISBN-13 válido + HTMX header → 200, contém título do livro no HTML
  - [ ] GET com DOI sem cadastro → sem flag `ja_no_acervo`
  - [ ] GET com DOI já cadastrado → flag setada e link para a análise existente
  - [ ] GET com ISBN já cadastrado → idem
  - [ ] GET sem `id` → 400 ou form vazio
  - [ ] Leitor não-promovido → 403

**Aceite**: lookup ao vivo funciona em dev tanto com DOI (`10.1016/j.cogsys.2012.05.003`) quanto com ISBN (`9780128038031`); permissão respeitada.

**Commit**: `feat(acervo): adiciona lookup HTMX no cadastro de artigo`

---

## M6 — Frontend: cadastrar_artigo aplica o mockup ⏱ G

O mockup já validou layout e UX. Agora portar para o template Django,
trocando fetch direto por HTMX para o backend.

- [ ] Migrar `templates/acervo/cadastrar_artigo.html` de `_base.html` → `_base_publico.html`
- [ ] Estrutura igual ao mockup:
  - [ ] header editorial (`.t-eyebrow` + `.t-h1` + `.t-prose`)
  - [ ] passo 1: radios DOI / ISBN / sem identificador + input grande mono (placeholder muda conforme radio selecionado: `10.xxxx/yyy` ou `978...`)
  - [ ] HTMX no input: `hx-get="{% url 'lookup_identificador' %}" hx-trigger="keyup changed delay:700ms" hx-target="#preview-card" hx-swap="innerHTML" hx-indicator="#lookup-spinner" hx-include="[name=tipoid]"` (envia o tipo selecionado pra view rotear)
  - [ ] passo 2: `<div id="preview-card">` recebe parcial
  - [ ] passo 3: form de metadados com `_form_metadados.html`
  - [ ] passo 4: botões "descartar" + "cadastrar e iniciar análise"
- [ ] Criar `templates/acervo/_preview_metadados.html`:
  - [ ] cartão com tipografia editorial (idêntico ao mockup, classe `.meta-card`)
  - [ ] **adapta layout conforme `tipo`**:
    - DOI/artigo: mostra periódico, volume, número, páginas, ISSN, citações
    - ISBN/livro: mostra editora, ano, ISBN-10/ISBN-13, páginas, capa (se houver)
  - [ ] resumo em `<details>` (colapsado por padrão)
  - [ ] badges de estado (encontrado / não encontrado / já no acervo)
- [ ] Criar `templates/acervo/_form_metadados.html`:
  - [ ] todos os campos do `ArtigoMetadadosForm` (incluindo `isbn`, `tipo_publicacao`)
  - [ ] valores pré-preenchidos a partir do lookup (via `value=` ou `initial`)
  - [ ] `tipo_publicacao` é definido automaticamente pelo lookup (artigo vs capítulo vs livro), mas editável
  - [ ] usar tokens `.field-input`, `.field-label` (definidos no mockup; mover para `input.css` em layer components — ver checklist abaixo)
- [ ] Em `static/css/input.css` `@layer components`: adicionar `.field-input`, `.field-label`, `.lookup-input`, `.meta-card`, `.meta-row`, `.step-indicator`, `.spinner` (extraídos do mockup)
- [ ] Rodar `tailwindcss -i static/css/input.css -o static/css/output.css` (ou comando do projeto) para regerar
- [ ] `python manage.py collectstatic --noinput`

**Aceite**: cadastrar um artigo via DOI **e** um livro via ISBN no dev funciona end-to-end pela tela nova; cartão de preview adapta-se ao tipo; visual fiel ao mockup; nenhum console error.

**Commit**: `style(acervo): aplica design editorial em cadastrar_artigo`

---

## M7 — Frontend: editar_analise + outras telas ⏱ G

Modernizar as 4 telas restantes. Aproveitar tokens já estendidos no M5.

- [ ] `templates/acervo/editar_analise.html`:
  - [ ] migrar para `_base_publico.html`
  - [ ] stepper editorial (4 passos numerados, indicador visual de concluído/atual/pendente)
  - [ ] cartão de identificação no topo com selo `.selo-aberto` ou `.selo-quebrado` baseado em `link_status`
  - [ ] auto-save indicator discreto: chip `.t-meta` no canto direito, atualiza com Alpine como hoje
  - [ ] passo "resenha" com fundo `.review-bg` (token já existe)
  - [ ] botão "submeter" com modal de confirmação Alpine
- [ ] `templates/acervo/minhas_analises.html`:
  - [ ] grid de cards (não tabela)
  - [ ] cada card: título, autor original, ano, chip de status (rascunho/submetida/em revisão/publicada)
  - [ ] criar `templates/acervo/_card_analise.html` reutilizável
- [ ] `templates/acervo/submeter_analise.html`:
  - [ ] tela de confirmação com checklist visual: "vai disparar sorteio de N revisores", "prazo X dias", "você receberá e-mail quando for revisada"
  - [ ] botão de confirmação destacado
- [ ] `templates/acervo/buscar_artigo.html` + `_busca_resultados.html`:
  - [ ] alinhar com vitrine (cards editoriais; tipografia consistente)
- [ ] Smoke test manual: clicar em todos os fluxos, comparar com vitrine pública para coerência visual

**Aceite**: as 4 telas usam `_base_publico.html`; nenhuma classe `bg-anco`/`text-slate-700` solta; testes manuais OK.

**Commit**: `style(acervo): aplica design editorial em editar_analise e demais`

---

## M8 — Tests E2E, cobertura, relatório, PR ⏱ M

- [ ] Tests E2E (Django test client, sem Selenium):
  - [ ] `test_cadastro_e_analise_completos.py`:
    - [ ] login analista → busca DOI → preview retornado → confirma → cria Artigo+Análise
    - [ ] login analista → busca ISBN → preview retornado → confirma → cria Artigo (capítulo/livro) + Análise
    - [ ] login analista → "sem identificador" → preenche manualmente → cria Artigo com `legacy:HASH`
    - [ ] edita análise (preenche presença, estrutura, resenha) → submete
    - [ ] verifica que `signal` disparou criação de Revisões
- [ ] `pytest --cov=apps/acervo` → cobertura ≥70% nas linhas novas
- [ ] `ruff check apps/ config/` zero warnings
- [ ] Atualizar `docs/ROADMAP.md` adicionando linha de "Frente UX Analista — concluída em YYYY-MM-DD"
- [ ] Criar `docs/relatorios/feat-analista-ux-crossref.md` no formato CLAUDE.md §7:
  - [ ] O que foi entregue (Crossref + ISBN + UX editorial)
  - [ ] Decisões tomadas (uma API por tipo de identificador; abstract/cobertura parcial → preenchimento manual em vez de cascata)
  - [ ] Desvios da especificação (cadastro sem DOI/ISBN não estava na spec original)
  - [ ] Dívida técnica
  - [ ] Métricas (cobertura, linhas adicionadas)
- [ ] `git push -u origin feat/analista-ux-crossref`
- [ ] Abrir PR para `main` com link para o relatório

**Aceite**: PR aberto, CI verde, relatório linkado.

**Commit (último)**: `docs: relatório da frente analista-ux-crossref`

---

## Mapa de dependências

```
M0 ──► M1 ─────► M3 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8
       (Crossref)│       (forms) (view) (cadastro) (demais) (E2E+PR)
                 │       ▲
       M2 ───────┘       │
       (ISBN)            │
                         │
                M3 ──────┘
                (model)

M1 e M2 podem ser feitos em paralelo (são serviços independentes).
M3 (model) só precisa começar quando M1 e M2 estiverem concluídos.
```

M1 e M2 são os únicos paralelizáveis. Os demais marcos são
estritamente sequenciais — cada um depende do anterior.

## Riscos / pontos de atenção

| Risco | Mitigação |
|---|---|
| Crossref offline durante teste/produção | Cache 24h + preenchimento manual já é o caminho oficial quando o lookup falha (ver M4) |
| OpenLibrary tem cobertura limitada para livros brasileiros | Aceito: ISBN não encontrado → analista preenche manualmente. Sem fallback — simplicidade > cobertura marginal. |
| Crossref retorna sem abstract (~50% dos casos) | Aceito: campo `resumo` fica vazio no preview, analista cola do PDF. Sem cascata de APIs. |
| ISBN com checksum inválido aceito por engano | Validação rigorosa no `validar_isbn()` antes de qualquer chamada de API |
| Migration M3 quebra dados existentes | Migration tem reverse_code; testada em factory de 1.443 reg. |
| Recompilar Tailwind quebra outras páginas | Adicionar tokens em `@layer components` (não em raiz) preserva isolamento |
| Sessão x form hidden no M5 | Decisão: form hidden é mais simples e idempotente; sessão fica de fora |
| Testes lentos com mock Crossref/OpenLibrary | Usar `unittest.mock.patch` com fixtures locais (não bater na API real em CI) |
| ISBN único pode colidir com outras edições do mesmo livro | `unique=True` no campo, mas curador pode fundir registros depois |

## Não faz parte deste roadmap (escopo separado)

- Redesign de `revisar.html` (revisão por pares) — escopo da próxima passada
- Dashboard de analista com métricas pessoais
- Exportação de análises em CSV/JSON
- Notificações por e-mail no momento do sorteio (já existe lógica básica; melhorar UX é fora de escopo)
- Integração de identificadores adicionais (DataCite para datasets, ROR para instituições) — possível extensão futura
