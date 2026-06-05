# Plano — Fase 12: Projetos (múltiplas revisões de escopo)

> **Status:** plano para revisão. Nada implementado ainda.
> **Objetivo:** permitir que a plataforma abrigue **mais de uma revisão de escopo**,
> cada uma com seu protocolo registrado, corpus, dedup, triagem, PRISMA e κ próprios;
> e que o **admin designe quais analistas trabalham em cada projeto**.

## 1. Motivação

Estratégias de busca diferentes são **revisões diferentes**: `"cognitive analysis"`
sozinho ≠ `"cognitive analysis" OR homônimos, BLOCO 1 AND BLOCO 2`. Cada uma exige
protocolo a priori, registro (OSF), fluxograma e concordância próprios — não se reporta
um único PRISMA para duas perguntas. Hoje o sistema é **mono-protocolo** (`ProtocoloTriagem.ativo()`
pega o primeiro registro). O esquema, porém, **já carrega `protocolo` como FK** em
`Busca`, `RegistroTriagem`, `SnapshotProtocolo`, `RodadaCalibracao`, e a unicidade de dedup
já é `(protocolo, identificador)`. Logo, isto é **evolução**, não reescrita.

## 2. Decisão de modelagem

**Elevar a própria `ProtocoloTriagem` a "Projeto"** (mantendo a tabela, evitando migração
estrutural grande). Ela já agrega buscas/registros/protocolo/calibração — passa a ser o
contêiner do projeto.

### 2.1 Campos novos em `ProtocoloTriagem`
- `nome` (curto, p/ UI) e `slug` (único, p/ URL).
- `estrategia_busca` (texto — a string/lógica que define a revisão; documental).
- `arquivado` (bool) — projetos concluídos somem dos seletores sem serem apagados.
- *(mantém)* `titulo`, `pergunta_pesquisa`, critérios, `versao`, `travado_em`,
  `registro_externo`, `usa_texto_completo` etc. — agora **por projeto**.
- `SnapshotProtocolo` continua dando o **versionamento interno** de cada projeto.

### 2.2 Membership — modelo `ProjetoMembro` (through)
```
ProjetoMembro(projeto FK, usuario FK, papel ∈ {curador, analista}, criado_em)
  UniqueConstraint(projeto, usuario)
```
Through-model (não M2M simples) porque o **papel é por projeto**: alguém pode ser
**curador do Projeto A** e **analista do B**. O `papel` global de `User`
(`leitor/analista/curador`) continua governando o acesso à plataforma; o papel **no
projeto** governa as ações da triagem daquele projeto.

### 2.3 O que permanece **global** (não duplicar)
- `Artigo` (acervo) e `Analise` (Matriz AnCo): a análise é intrínseca ao artigo. Dois
  projetos podem **incluir o mesmo artigo** e reusam o mesmo `Artigo` (promoção já é
  idempotente). Projetos diferem só na **triagem que selecionou** o artigo.
- Usuários, vocabulários/bases, aprovação de revisor (`revisor_aprovado`).

## 3. Aposentar o `ativo()` — seleção explícita por URL

Substituir `ProtocoloTriagem.ativo()` por **escopo de URL**:
`/triagem/p/<slug>/...` (importar, duplicatas, triar, prisma, protocolo, calibração).
Vantagens: links compartilháveis, sem estado oculto de sessão, e o helper de permissão
recebe o projeto explicitamente. `/triagem/` (raiz) vira a **lista de projetos** do usuário.

**Pontos de toque do `ativo()`** (13 hoje, todos a parametrizar pelo slug):
`apps/core/views.py:155` (painel), `management/commands/importar_triagem.py:63`,
e `apps/triagem/views.py` linhas 78, 99, 203, 228, 293, 318, 437, 476, 507, 575, 604.

## 4. Permissões por membership (inclui a regra de dedup adiada)

Hoje `_eh_curador` = `is_staff or user.eh_curador` (global) e `revisores_elegiveis`/
`calibracao.revisores_da_equipe` filtram **todos** os aprovados. Passam a ser **por projeto**:

- **Curador do projeto** = `ProjetoMembro.papel==curador` **ou** `is_staff` (admin vê tudo).
  Substitui `_eh_curador(user)` por `eh_curador_no(projeto, user)` nas ações gated
  (iniciar triagem, desempate, protocolo, calibração).
- **Sorteio restrito aos membros**: `revisores_elegiveis(registro)` passa a filtrar
  `ProjetoMembro(projeto=registro.protocolo, usuario=...)` **∩** `revisor_aprovado=True`
  (mantém a aprovação global como pré-requisito).
- **Dedup (regra adiada da Fase 11):** resolver duplicatas exige ser **membro do projeto**;
  pares **dentro das bases do próprio importador** → qualquer membro importador; pares
  **cruzados** → **curador do projeto**. A trilha de auditoria (quem/quando), a procedência
  e o desfazer já existem (entregues agora); aqui só entra o **gate** por membership.

## 5. Sub-fases sugeridas

| Sub-fase | Entrega |
|---|---|
| **12.0** | Modelo: `nome/slug/estrategia_busca/arquivado` + `ProjetoMembro`; **migração de dados** (protocolo atual → "Projeto 1" com slug; membros = usuários ativos hoje). |
| **12.1** | Escopo por URL `/triagem/p/<slug>/`; aposentar `ativo()` nos 13 pontos; lista de projetos em `/triagem/`. |
| **12.2** | Permissões por membership (`eh_curador_no`, sorteio por membro, calibração por membro). |
| **12.3** | UI: criar projeto (curador/admin), tela do admin para **designar membros/papéis**, seletor/breadcrumb de projeto. |
| **12.4** | **Gate de dedup por membership** (regra adiada da Fase 11). |
| **12.5** | Docs (`docs/relatorios/fase-12.md`, CLAUDE.md, addendum), testes, deploy. |

## 6. Migração de dados (12.0) — sem perda

1. Criar colunas novas com defaults; backfill `nome="Análise Cognitiva"`,
   `slug="analise-cognitiva"` no protocolo existente.
2. Popular `ProjetoMembro` com os usuários ativos atuais (curadores → `curador`,
   demais analistas → `analista`); admins via `is_staff`.
3. Tudo aditivo; nenhuma alteração em `acervo`/`Analise`; legado intocado.

## 7. Riscos e cautelas

- **Transversalidade:** toca todas as views da triagem — fazer em PRs pequenos por sub-fase,
  com a suíte verde a cada passo (hoje 126 testes na triagem).
- **Links antigos:** rotas `/triagem/duplicatas/` etc. passam a exigir slug. Mitigar com
  redirecionamento do projeto default enquanto houver 1 só projeto.
- **`importar_triagem` (management command):** ganha argumento `--projeto <slug>`.
- **Não superdimensionar:** sem papéis além de curador/analista por projeto; sem
  permissões granulares por base. Construir o mínimo e parar.

## 8. Decisões — TRAVADAS (2026-06-04)

1. **Escopo por URL** `/triagem/p/<slug>/...` ✅
2. **Rótulo na interface:** "Projeto" ✅
3. **Quem cria projeto:** só admin (`is_staff`) ✅
4. **Aprovação de revisor:** global (`revisor_aprovado`) **+** membership do projeto ✅
5. **Acervo/análise globais** (mesmo artigo pode ser incluído por 2 projetos; uma análise
   por artigo; acervo único) ✅

---

**Próximo passo:** começar pela **12.0** (modelo + migração de dados), validar a suíte e
parar para conferência do "Projeto 1" antes de seguir para 12.1.
