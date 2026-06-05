# Relatório — Fase 11: Rigor metodológico para periódicos de alto impacto

Eleva a triagem (Fases 9–10) ao padrão exigido por revisões de escopo publicáveis:
**concordância entre revisores reportável**, **checklist PRISMA-ScR**, **protocolo
registrado e versionado (a priori)**, **triagem em duas etapas (título/resumo → texto
completo)** e **calibração (piloto)** antes do run real.

Tudo **aditivo** e, onde estrutural, **opt-in**: o fluxo de etapa única em uso continua
idêntico por padrão (`protocolo.usa_texto_completo=False`).

## Sub-fases

| Sub-fase | Entrega | Status |
|---|---|---|
| **11.1** | **Concordância entre revisores**: κ de **Fleiss** + % de acordo (escala de Landis & Koch), no fluxograma PRISMA e nos exports CSV/JSON. Fleiss (não Cohen) porque os pares de revisores variam por registro (sorteio). | ✅ |
| **11.2** | **Checklist PRISMA-ScR** (Tricco et al., 2018 — 22 itens; 12 e 16 opcionais em escopo) em `/triagem/checklist/`, indicando **onde o AnCo apoia cada item** + export CSV. | ✅ |
| **11.3** | **Protocolo a priori**: registro externo (OSF), **versionamento e trava** (snapshot auditável por versão) em `/triagem/protocolo/`. | ✅ |
| **11.4** | **Triagem em duas etapas** (opt-in): título/resumo → texto completo, com razões de exclusão por etapa, sorteio do 2º estágio, desempate por etapa e contagens PRISMA das duas etapas. | ✅ |
| **11.5** | **Calibração (piloto)**: toda a equipe tria uma amostra comum; mede-se κ; gate de prontidão (κ ≥ 0,60). Decisões isoladas (etapa `CALIBRACAO`), sem poluir o run real. | ✅ |

## Como cada peça funciona

### 11.1 Concordância (`apps/triagem/concordancia.py`)
- `fleiss_e_acordo(itens, n)` é o núcleo reutilizável (κ de Fleiss + % de acordo).
- `calcular(protocolo, etapa=TA)` agrupa as decisões **concluídas** por registro,
  considera os itens com exatamente `n_revisores` decisões e devolve κ, % de acordo,
  interpretação e distribuição. Aparece em `/triagem/prisma/` e nos exports.

### 11.2 Checklist (`apps/triagem/checklist.py`)
- `ITENS`: os 22 itens com seção, descrição, **link para onde o AnCo cobre** o item
  (protocolo, painel, PRISMA, estatísticas) e marcação de opcional (12 e 16).
- `/triagem/checklist/` renderiza por seção; `?formato=csv` exporta.

### 11.3 Protocolo versionado (`ProtocoloTriagem` + `SnapshotProtocolo`)
- Campos novos: `registro_externo` (URL/OSF), `versao`, `travado_em`, `usa_texto_completo`.
- `travar(user)` congela um **snapshot** (`SnapshotProtocolo` — JSON dos critérios)
  da versão; `abrir_nova_versao()` incrementa a versão e destrava para edição.
- `/triagem/protocolo/`: curador edita registro/etapas, trava e abre novas versões;
  histórico de versões travadas é auditável (admin inline também).

### 11.4 Duas etapas (estrutural, **opt-in**)
- `DecisaoTriagem.etapa` ∈ {`ta` título/resumo, `tc` texto completo, `ca` calibração};
  unicidade agora é `(registro, revisor, etapa)`.
- Novos status de `RegistroTriagem`: `INCLUIDO_TA` (passou no T/R, aguardando texto),
  `EM_TEXTO` (em triagem de texto completo), `EXCLUIDO_TC` (excluído no texto, com razão).
- `aprovacao.consolidar_regstro` + `destino()` centralizam a transição (consenso **e**
  desempate usam a mesma regra). 1ª etapa + protocolo de 2 estágios + incluir →
  `INCLUIDO_TA`, que dispara automaticamente o **sorteio da 2ª etapa**; 2ª etapa incluir
  → `INCLUIDO` (promove ao acervo); excluir → `EXCLUIDO_TC` com motivo.
- `sorteio.executar_sorteio(registro, etapa)` e `tasks.avancar_apos_status` cobrem os dois
  estágios; `re_sortear` e desempate são por etapa. PRISMA conta os dois estágios.
- UI: `triar.html` mostra a etapa (banner) e, no texto completo, um botão destacado
  "Abrir texto completo"; `prisma.html` exibe a 2ª caixa de triagem quando ativa.

### 11.5 Calibração (`apps/triagem/calibracao.py` + `RodadaCalibracao`)
- `iniciar_calibracao(protocolo, tamanho)` sorteia uma amostra de registros
  `identificado` e designa **toda a equipe** (decisões etapa `CALIBRACAO`), **sem mudar o
  status** dos registros (entram no run real normalmente).
- `calcular(rodada)`/`fechar_calibracao(rodada)` medem κ de Fleiss sobre a amostra e
  marcam prontidão (κ ≥ 0,60). `/triagem/calibracao/` (curador inicia/fecha).
- Isolamento garante que a calibração **não afeta** o κ oficial (etapa T/R) nem o PRISMA.

## Critério de aceite
- [x] Concordância (κ de Fleiss) reportável no PRISMA e nos exports.
- [x] Checklist PRISMA-ScR completo (22 itens) + export.
- [x] Protocolo com registro externo, versão e trava (snapshot a priori).
- [x] Triagem em duas etapas opt-in, sem alterar o fluxo de etapa única padrão.
- [x] Calibração/piloto com gate de κ antes do run real.

## Decisões de implementação
- **Fleiss**, não Cohen: os pares de revisores variam por registro (sorteio aleatório),
  então o nº de avaliadores por item é fixo mas os avaliadores diferem — caso de Fleiss.
- Duas etapas **opt-in** por `usa_texto_completo` (default `False`): preserva 100% do
  comportamento atual; ligar a flag passa a exigir o 2º estágio dos novos incluídos.
- `INCLUIDO_TA` é status **não-terminal**: `decisao_final`/`decidida_em` só são gravados
  nos status terminais (`INCLUIDO`/`EXCLUIDO`/`EXCLUIDO_TC`).
- Calibração reusa `DecisaoTriagem` com etapa própria em vez de um modelo de decisão
  paralelo — menos superfície, e o `triar.html` já é etapa-aware.
- `gate` de calibração em **κ ≥ 0,60** (substancial, Landis & Koch) — limiar usual; o
  curador decide com base no número exibido.

## Desvios da especificação
Nenhum. A Fase 11 estende o addendum de triagem (Fases 9–10) sem alterar o modelo
`Analise` nem o acervo. A 2ª etapa e a calibração são novas, opcionais e isoladas.

## Dívida técnica deixada
- O **re-sorteio por prazo** (`task_verificar_prazos_triagem`) cobre as duas etapas, mas
  não há ainda um lembrete específico de "texto completo pendente" além do e-mail de
  sorteio. Aceitável para o run inicial.
- A concordância exibida no PRISMA é a da **1ª etapa** (T/R); a κ da 2ª etapa pode ser
  adicionada ao relatório se houver volume suficiente.

## Métricas / verificação
- Migrations: `0014` (registro externo/versão/trava/2 etapas + `SnapshotProtocolo`),
  `0015` (status de 2 etapas + `etapa` em `DecisaoTriagem` + nova unicidade),
  `0016` (etapa `CALIBRACAO` + `RodadaCalibracao`).
- Testes novos: concordância, checklist+protocolo, duas etapas e calibração.
  Suíte completa: **471 passed, 1 skipped, 1 xpassed**. `ruff` limpo; `manage.py check` ok.
- Aditivo: nenhuma alteração no schema de `acervo`/`Analise`; legado isento.

## Pendências para o usuário
- **Testar o fluxo** ponta a ponta (você pediu para deixar tudo pronto):
  1. `/triagem/protocolo/` — preencher registro OSF, **travar a versão**; opcionalmente
     ligar **"2ª etapa (texto completo)"**.
  2. `/triagem/calibracao/` — iniciar um piloto (ex.: 10 itens), pedir à equipe que trie,
     conferir o **κ** e fechar.
  3. `/triagem/checklist/` — conferir o checklist e exportar o CSV para o manuscrito.
  4. Rodar a triagem real; conferir `/triagem/prisma/` (com as duas etapas, se ativadas).
- Decidir se o run inicial usará **uma ou duas etapas** (a flag pode ser ligada antes de
  iniciar a triagem).
