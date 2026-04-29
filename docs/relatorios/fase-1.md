# Relatório — Fase 1: Núcleo de dados e admin

**Data**: 2026-04-29
**Branch**: `fase-1-modelagem-base` (a partir de `fase-0-fundacao`)
**Commits**: 5 atômicos por área de domínio

## O que foi entregue

### Modelos de domínio (3 apps Django sob `apps/`)

- **`apps.core`**:
  - `User` — estende `AbstractUser` com `nome_exibicao`, `vinculo_institucional`,
    `grupo_pesquisa`, `orcid`, `papel` (leitor/analista/curador),
    `aceita_revisoes`, `limite_revisoes_simultaneas`, `eh_legado`. Helpers
    `eh_curador` e `eh_analista`.
  - `SolicitacaoCadastro` — pedido de promoção a analista (será exercitado
    na Fase 2).
- **`apps.vocabulario`**:
  - `Vocabulario` (codigo + nome + descricao).
  - `TermoVocabulario` (nome, sinonimos: `ArrayField[CharField(200)]`,
    ativo). Método `buscar_canonico(codigo, valor)` resolve por nome ou
    sinônimo, case-insensitive.
- **`apps.acervo`**:
  - `Artigo` — referência bibliográfica, **DOI único**, link de acesso,
    status do link, `eh_legado`, FK para `TermoVocabulario` da base.
  - `SnapshotLink` — captura no Wayback Machine.
  - `Analise` — campos de presença, pertinência, estrutura (objeto,
    objetivo, foco, metodologia, M2M com epistemologia/teoria),
    `resenha_critica` autoral com cache `tem_resenha`. Constraint
    `(artigo, analista)` única. **Histórico via `simple_history.HistoricalRecords`**.
  - `Revisao` — tipo (estrutural/cega), parecer, prazo. Constraint
    `(analise, revisor, tipo)` única.
  - `ComentarioRevisao` — comentário ancorado por campo da análise.

### Migrations
- `apps/core/migrations/0001_initial.py`
- `apps/vocabulario/migrations/0001_initial.py`
- `apps/acervo/migrations/0001_initial.py` + `0002_initial.py` (FKs cruzadas)
- Aplicadas com sucesso após reset do volume `pgdata` (necessário porque
  Phase 0 já tinha aplicado `auth/admin/contenttypes/sessions` antes do
  `core.User` existir — incompatível com `AUTH_USER_MODEL` introduzido
  agora).

### Admin Django configurado

- `UserAdmin` estende o do Django com fieldset "Perfil AnCo".
- `ArtigoAdmin` com `list_display`, `list_filter` (status do link, ano,
  base), busca por título/DOI/autores, inline de `SnapshotLink`.
- `AnaliseAdmin` estende `SimpleHistoryAdmin` (botão History nativo),
  9 fieldsets agrupando os campos, inline de `Revisao`, `filter_horizontal`
  para epistemologia/teoria.
- `RevisaoAdmin` com inline de comentários.
- `Vocabulario`/`TermoVocabulario` com inline de termos e edição rápida
  de `ativo` na listagem.
- **Validação**: todas as 9 listagens admin retornam HTTP 200 com
  superusuário logado.

### `django-simple-history` integrado

- Adicionado a `INSTALLED_APPS` e `MIDDLEWARE`.
- `Analise.history` ativado — testes confirmam 3 versões após criar+2 saves.

### Fixtures iniciais (vocabulários)

- `apps/vocabulario/fixtures/vocabularios_iniciais.json` com:
  - 4 `Vocabulario`: base, epistemologia, teoria, area
  - 14 `TermoVocabulario` canônicos (Web of Science/WOS, Scopus,
    Science Direct/Elsevier, Redalyc, Sage, Repositório UFBA, PubMed,
    Empirismo + 5 variantes, Construtivismo/Socio/Neuro, Cognição,
    Neurociência cognitiva, Psicologia cognitiva). Sinônimos calibrados
    pelos dados reais do JSON legado.

### Análise exploratória do legado

`docs/migracao/analise_legado.md` (CLAUDE.md §9.1) com estatísticas reais:
1.443 registros, 4 anos inválidos, 121 sem DOI, 47 com prefixo "DOI:",
234 com URL no campo DOI, 23 ISSN no campo DOI, 1.062 sem link,
1.033 sem analista, 1.257+ epistemologia/teoria vazios, 12 variantes
de bases, 94 nomes únicos de analistas com variantes de capitalização.

### Migrador `migrate_legacy.py` (idempotente)

`python manage.py migrate_legacy [--path X] [--dry-run] [--limit N]`

Helpers de normalização (todos com testes parametrizados):
- `normalizar_ano`, `normalizar_doi` (strip prefixo, extrai de URL,
  rejeita ISSN), `gerar_id_legado` (SHA1 16-chars determinístico),
  `para_booleano` (8+ variantes), `texto_limpo`,
  `normalizar_nome_analista` (Title Case + heurística anti-corrupção).

Idempotência via `update_or_create`:
- `Artigo` por `doi` (canônico ou `legacy:HASH`)
- `User` legado por `username` (slug)
- `Analise` por `(artigo, analista)`

Vocabulário: `resolver_ou_criar_termo` busca canônico via sinônimos;
se não match, cria com `ativo=False`.

**Execução real contra os 1.443 registros**:
- 951 Artigos legado, 1.095 Análises legado, 81 Users (1 anônimo + 80 nominais)
- 884 DOIs canônicos, 559 IDs gerados (`legacy:`)
- 4 anos inválidos→null, 1.062 sem link (esperado)
- Segunda execução: 1.443 atualizadas, 0 erros, 0 criações novas → **idempotência confirmada**

## Critério de aceite (da especificação §10 — Fase 1)

- [x] Modelos completos (incluindo `SnapshotLink` e campo `resenha_critica`)
- [x] Migrations geradas e aplicadas
- [x] Admin Django configurado para os 9 modelos
- [x] `django-simple-history` integrado em `Analise`
- [x] Vocabulários iniciais via fixture
- [x] Script `migrate_legacy.py` funcionando para 1.443 registros
- [x] **Aceite formal**: `manage.py migrate_legacy` importa tudo; admin navegável

## Decisões tomadas

- **Apps namespacing**: `apps.core` etc. (não `core`). Mantém `apps/` como
  pacote Python isolando todo o código de domínio.
- **`User.eh_legado`**: campo extra além do que a spec previa. Permite
  filtrar/desativar contas placeholder no admin sem heurística por nome.
- **`Artigo.eh_legado`**: idem, marca registros importados.
- **`User.is_active=False` para legado**: não permite login até que o
  curador (ou o próprio usuário, na fusão da Fase 2) decida o que fazer.
- **`Analise.tem_resenha` no `save()`**: cache atualizado automaticamente
  ao salvar (não via signal — mais simples e testável). Spec §4.2
  sugeria signal mas o efeito é o mesmo.
- **Heurística anti-corrupção em `normalizar_nome_analista`**: valores
  >120 chars ou com pontuação excessiva são tratados como dados
  corrompidos (descrição de artigo no campo errado — caso real em 2
  registros do legado) e roteados ao `legado-anonimo`. Sem isso, falhava
  por `value too long for varying(200)` no `nome_exibicao`.
- **Termos não-canônicos como `ativo=False`** em vez de descarte: preserva
  o dado bruto do legado para curadoria posterior. Curador pode fundir,
  promover ou desabilitar.
- **`legado-anonimo` único** para os 1.033 registros sem analista:
  evita inflar a base de usuários com placeholders por registro.
- **Volume `pgdata` foi dropado uma vez** durante a Fase 1 para resolver
  inconsistência de migrations (Phase 0 migrara `auth/admin` antes de
  `core.User` existir). Em produção isso não acontecerá — `core` será
  uma das primeiras migrations aplicadas.
- **Reset do banco entre rodadas de migração**: cuidado se rodar
  `migrate_legacy` após mudar normalizações (gera novos hashes
  `legacy:`). Idempotente para entrada estável; sensível a mudanças no
  algoritmo de hash.

## Desvios da especificação

- **`User.is_active=False` para legado**: spec §8.2 pedia "User legado
  para analistas sem conta, papel `leitor`, e-mail placeholder, sem
  senha utilizável". Adicionei `is_active=False` para garantir que esses
  placeholders **não conseguem fazer login** mesmo se alguém setar uma
  senha por engano. Spec não explicitou, mas a intenção é clara.
- **`Vocabulario` ganhou `criado_em`**, `TermoVocabulario` também (auto_now_add).
  Spec não previa, mas é trivial e ajuda em auditoria.
- **`Vocabulario.codigo` é `SlugField(max_length=50)`** (a spec não
  especificou tamanho). 50 chars é mais que suficiente para códigos
  curtos como `epistemologia`, `base`, `area`.

## Dívida técnica deixada

- **Termos do legado com `ativo=False`**: a primeira execução criou ~290
  termos não-canônicos (epistemologia + teoria) que precisam ser
  revistos pelo curador. Não há ainda uma tela específica para isso (admin
  resolve, mas não é otimizado).
- **Análises sem analista identificado** (1.036 vinculadas a `legado-anonimo`):
  spec §8.3 propõe "Reivindicação de autoria" quando analista esperado
  se cadastra. Implementação fica para a Fase 2 (cadastro/auth).
- **Texto solto em campos S/N**: alguns textos longos do legado foram
  preservados em `aspectos_relevantes` e `definicao_extraida` com prefixo
  `[do campo Pertinência]`. Curador pode reescrever depois.
- **Falta tela de "fila de espera"** para análises com `eh_legado=True`
  que precisam de revisão (Fase 4).

## Métricas

- **Cobertura de testes**: 96% (602 statements, 24 misses; misses
  concentrados em `__str__` e branches de erro raros).
- **86 testes passando**: 47 unitários de helpers, 16 de modelos,
  8 de busca canônica, 11 end-to-end do migrador, 4 de smoke (Phase 0).
- **Linhas adicionadas**: 2.664 (sobre fase-0-fundacao).
- **Arquivos criados**: 36 (módulos Django + migrations + fixtures + testes + docs).
- **Tempo aproximado da fase**: 1h (de extremo-rápido devido à boa
  preparação na Fase 0 e à análise exploratória feita upfront).

## Pendências para o usuário

Não-bloqueantes para iniciar a Fase 2, mas valeria atenção:

1. **Revisar a fixture `vocabularios_iniciais.json`** antes de uso em
   produção. Os termos de epistemologia/teoria foram inferidos da base
   real mas refletem só as variantes mais frequentes; o curador
   provavelmente vai querer ampliar/ajustar.
2. **Revisar os ~290 termos `ativo=False`** criados pela importação real.
   Listagem em `/admin/vocabulario/termovocabulario/?ativo__exact=0` com
   `list_editable = ('ativo',)` para edição rápida.
3. **Decidir política de fusão de analistas**: 81 users legado ainda têm
   variantes de capitalização que podem corresponder à mesma pessoa
   (`Regis Glauciane` vs `Regis Glauciane Souza` aparecem como contas
   distintas). Spec §8.3 propõe reivindicação na hora do cadastro — pode
   precisar de UI dedicada de fusão no admin.
4. **Política para os 559 artigos com `legacy:HASH`**: idealmente, com
   tempo, o curador identifica DOIs reais para alguns; a constraint
   permite atualizar `doi` mas requer cuidado com rotas externas. Decisão
   de produto, não de código.

**Aprovação para iniciar a Fase 2** (Autenticação Google + cadastro
institucional + tela de promoção) é o próximo passo.
