# Levantamento retroativo de decisões — desenvolvimento da Plataforma AnCo com apoio de IA

> **Para que serve este documento.** Reunir, a partir das evidências que o
> próprio projeto deixou (commits, relatórios de fase, pareceres, memórias
> persistentes da IA e o banco de produção), o **inventário das decisões**
> tomadas entre 29/04/2026 e 08/07/2026, com data, alternativa descartada,
> justificativa, quem decidiu e onde está a evidência. É insumo para um
> **artigo de relato de experiência** sobre desenvolver uma plataforma de
> pesquisa acadêmica em parceria com um agente de IA — não é o artigo.
>
> Levantamento produzido em 03/09/2026.

---

## 1. Método do levantamento

### 1.1. Fontes de evidência usadas

| Fonte | Volume | O que dá |
|---|---|---|
| Histórico Git (`main`) | 332 commits, 29/04–08/07/2026 | cronologia, granularidade, reversões, co-autoria da IA |
| `docs/relatorios/fase-*.md` | 25 relatórios | seções fixas "Decisões tomadas", "Desvios da especificação", "Dívida técnica" |
| `docs/planos/*.md` | 5 planos | decisões **travadas antes** de implementar |
| `PARECER_*.md`, `INVESTIGACAO_*.md` (raiz de `~`) | 4 documentos | análises pedidas à IA **antes** de decidir |
| `docs/relatorios/auditoria-tecnica-2026-06.md` | 1 | autoavaliação crítica solicitada pelo usuário |
| `docs/especificacao/ESPECIFICACAO.md` (§ Histórico de versões + addenda) | v1 → v2.2 + 3 addenda | mudanças de escopo formalizadas |
| `CLAUDE.md` | 21 KB, 12 seções | o **contrato de processo** com o agente |
| Memória persistente do agente (`~/.claude/.../memory/*.md`) | 13 memórias + 4 antigas | decisões do usuário com o "porquê" registrado |
| Banco de produção (`infra-db-1`) | consultas só-leitura | uso real em 03/09/2026 |

### 1.2. Convenções

- Cada decisão recebe um **ID** (`D01`…) para citação no artigo.
- **Quem decidiu** distingue quatro instâncias, que o projeto manteve separadas
  de forma explícita: **U** (usuário/desenvolvedor), **C** (coordenação
  acadêmica — profas. Fróes, Leliana, Cláudia), **E** (curadoria bibliográfica —
  Dra. Eneida Santana), **IA** (decisão do implementador, registrada em
  relatório). `U←IA` = a IA propôs, o usuário decidiu.
- Onde o documento infere algo não escrito em nenhuma fonte, o texto diz
  **(inferência)**.

### 1.3. Limites da base de evidência

- **As transcrições das sessões não foram preservadas.** O diretório de
  sessões do agente guarda apenas a sessão corrente; não há registro de
  prompts, de tentativas descartadas dentro de uma sessão, nem de tempo de
  interação. Tudo o que este levantamento reconstrói é o **resultado
  commitado** e o que foi deliberadamente escrito em documento.
- Não há registro de **esforço** (horas por fase). As estimativas em dias no
  ROADMAP são *previsões*, não medições.
- O `churn` do Git mistura código e dados (o legado JSON sozinho responde por
  ~121 mil linhas). Onde importa, este documento separa o churn de `.py`/`.html`.

---

## 2. Linha do tempo em cinco eras

| Era | Período | Dias com commit | Commits | Linhas `.py`/`.html` | Caráter |
|---|---|---|---|---|---|
| **0 — Contrato** | 29/04 (antes do código) | — | — | — | escrever as regras do trabalho com a IA |
| **1 — Fundação** | 29/04 – 01/05 | 3 | 74 | 17.193 | Fases 0–8 quase inteiras |
| **2 — Confronto com o uso real** | 03/06 – 08/06 | 6 | 165 | 25.408 | triagem, PRISMA, reversões de fluxo |
| **3 — Separação estrutural** | 14/06 – 17/06 | 2 | 30 | 6.331 | ANCO × PRISMA em módulos |
| **4 — Fidelidade conceitual** | 02/07 – 08/07 | 6 | 63 | 7.775 | Fróes, tutorial das professoras, UX do analista |

Commits por dia (todos os 16 dias efetivos):

```
2026-04-29  58    2026-06-05  15    2026-06-17   6
2026-04-30  12    2026-06-06  28    2026-07-02   3
2026-05-01   4    2026-06-07   7    2026-07-05   9
2026-06-03  32    2026-06-08  42    2026-07-06  16
2026-06-04  41    2026-06-14  24    2026-07-07  18
                                    2026-07-08  17
```

**Dado central para o artigo:** 71 dias corridos, **16 dias de trabalho
efetivo**, dois hiatos longos (01/05→03/06 e 08/06→14/06, 17/06→02/07). O
desenvolvimento não foi contínuo: foi **episódico e em blocos densos**, com
cada bloco disparado por um evento externo (uma reunião, um tutorial recebido,
um problema relatado por analista).

---

## 3. Era 0 — O contrato de trabalho com a IA (o achado mais reutilizável)

Antes da primeira linha de código, o projeto escreveu um documento que governa
o **processo** do agente, separado da especificação que governa o **produto**.
Essa separação é, em si, a primeira decisão.

| ID | Decisão | Alternativa descartada | Por quê | Quem | Evidência |
|---|---|---|---|---|---|
| D01 | Dois documentos canônicos com precedência declarada: `ESPECIFICACAO.md` prevalece para produto, `CLAUDE.md` para processo | um único documento | evita que o agente "reescreva o produto" ao ajustar o processo | U | `CLAUDE.md` §1 |
| D02 | **Trabalho faseado** (0–7), uma fase por vez, **parada obrigatória** para aprovação humana entre fases; proibido implementar código de fase futura | desenvolvimento contínuo dirigido pelo agente | mantém o humano no controle de escopo; torna o trabalho auditável em blocos | U | `CLAUDE.md` §2 |
| D03 | **Relatório de Fim de Fase obrigatório** com seções fixas: *o que foi entregue, critério de aceite, decisões tomadas, **desvios da especificação**, dívida técnica deixada, métricas, pendências para o usuário* | changelog livre | força o agente a **declarar onde divergiu** e o que adiou — é o instrumento que tornou este levantamento possível | U | `CLAUDE.md` §7; 25 relatórios |
| D04 | Regra explícita de **quando perguntar e quando não**: produto e trade-offs visíveis → perguntar com 2-3 opções; detalhe técnico interno → decidir e documentar | perguntar sempre / nunca | calibra a autonomia; reduz interrupção sem perder governança | U | `CLAUDE.md` §8.1–8.2 |
| D05 | Tom contratado: "*se discordar da especificação, diga e proponha alternativa — você é o implementador, não um executor passivo*" | agente puramente executor | autoriza a IA a contestar o escopo — usado nos pareceres (§6) | U | `CLAUDE.md` §8.3 |
| D06 | **Execução autônoma dentro de fase aprovada**: aprovado o plano, o agente executa tudo (commits, builds, testes) sem confirmações intermediárias | confirmação passo a passo | "*execute todas as ações no âmbito dessa fase sem me perguntar*" (29/04) | U | memória `feedback_execucao_autonoma` |
| D07 | Variante por fase: "*só faça git ao final da fase, execute toda a fase sem interrupção, teste ao final*" — sobrescreve a convenção de commit atômico | commits incrementais (§4 do próprio CLAUDE.md) | o usuário sobrepôs o contrato para uma fase específica — precedente de **contrato mutável em tempo de execução** | U | mesma memória |
| D08 | **Co-autoria da IA declarada** em todo commit (`Co-Authored-By:`) | autoria silenciosa | rastreabilidade da participação da IA: **344 trailers em 332 commits** | U | `git log` |
| D09 | Testes obrigatórios em validações, services de domínio e fluxos críticos; **cobertura ≥70% do código novo por fase**; CI (ruff + pytest) desde a Fase 0 | testes ao final | trava de qualidade que o agente não pode negociar ("não desabilite checks do CI") | U | `CLAUDE.md` §6, §10 |
| D10 | Lista de proibições explícitas: sem dependência sem justificativa **no commit**, sem abstração especulativa, sem `print()`, sem reescrever a especificação por conta própria | confiar no julgamento do agente | contém os vícios típicos de geração automática (over-engineering, dependências gratuitas) | U | `CLAUDE.md` §10 |
| D11 | **Memória persistente** do agente em arquivos versionáveis, cada uma com *Why* e *How to apply* | contexto reconstruído a cada sessão | 16 dias de trabalho em 71, com hiatos de até 5 semanas: a memória é o que atravessa o hiato | U←IA | `~/.claude/projects/.../memory/` |
| D12 | Preferência declarada: **"sempre a solução profissional, não a gambiarra"** — apresentar patch e correção de raiz com veredito honesto, inclusive chamando a própria proposta de gambiarra | aceitar o remendo mais barato | "*essa proposta é profissional ou gambiarra?*" — o usuário escolheu a refatoração estrutural (abas client-side) | U | memória `preferencia-solucoes-profissionais` |

---

## 4. Era 1 — Fundação (29/04 – 01/05): oito fases em três dias

**58 commits e 11.399 linhas de `.py`/`.html` em 29/04** — Fases 0 a 8 (fundação,
modelagem, auth, análises, revisão por pares, acervo público, saúde de links,
produção e busca semântica). O deploy em produção aconteceu **no mesmo dia** em
que o projeto nasceu.

### 4.1. Decisões de stack e infraestrutura

| ID | Decisão | Alternativa | Por quê | Quem |
|---|---|---|---|---|
| D13 | Django 5 + PostgreSQL 16 + Redis + Docker Compose + Caddy | — | stack fixada na especificação antes do código | U |
| D14 | `setuptools` + `pyproject.toml` | Poetry / PDM | "menor superfície, suficiente para Django, sem lock file dedicado nesta fase" | IA |
| D15 | `psycopg` 3 (binary) | `psycopg2-binary` | mantido oficialmente, compatível com Django 5 | IA |
| D16 | Django pinado `>=5.0,<5.2` | seguir a última | pin conservador até haver cobertura | IA |
| D17 | Compose mínimo (web+db+cache): **Caddy adiado à Fase 7, worker à Fase 4** | compose completo desde a Fase 0 (era o que a spec dizia) | escopo enxuto aprovado pelo usuário; serviço sem dependência entraria em loop de erro | U←IA |
| D18 | `/healthz` fora do plano original | — | smoke público reaproveitado por teste e load balancer | IA |
| D19 | Identidade Git isolada em `/tmp/gitconfig-claude` via `GIT_CONFIG_GLOBAL` | alterar `~/.gitconfig` do host | o usuário proibiu tocar na configuração do host (root operando em diretório de outro usuário) | U |
| D20 | Frontend: templates Django + **HTMX + Alpine + Tailwind**; Tailwind via CDN na Fase 3 | SPA (React/Vue); pipeline npm | "economia de complexidade — sem container Node, sem npm install no build" | IA |

### 4.2. Decisões de domínio e dados

| ID | Decisão | Alternativa | Por quê | Quem |
|---|---|---|---|---|
| D21 | A plataforma **não hospeda obras de terceiros** — só metadados e links; o conteúdo autoral hospedado é a análise e a resenha (CC-BY-NC) | repositório de PDFs | decisão jurídica/editorial anterior ao código | U |
| D22 | **URLs estáveis e citáveis desde o dia 1** (`/artigo/<doi-slug>/`, `/analise/<id>/`) | estabilizar depois | "mudança de URL depois quebra citações" | U |
| D23 | Migrador do legado **idempotente**, logando toda normalização, sem silenciar nada | import único | 1.443 registros com inconsistências catalogadas | U |
| D24 | Termos não canônicos importados como `ativo=False` | descarte | preserva o dado bruto para curadoria posterior | IA |
| D25 | Usuário único `legado-anonimo` para 1.033 registros sem analista | um placeholder por registro | evita inflar a base de usuários | IA |
| D26 | Heurística anti-corrupção em `normalizar_nome_analista` (>120 chars ou pontuação excessiva → anônimo) | falhar na importação | caso real: descrição de artigo no campo do analista, estourando `varchar(200)` | IA |
| D27 | Campos `eh_legado` em `User` e `Artigo` (não previstos na spec) | heurística por nome | permite filtrar/bloquear sem adivinhação — base da regra D45 | IA |
| D28 | Auto-save no **cliente** (Alpine + endpoint JSON dedicado), recusando análises não-rascunho | `hx-trigger` por campo | previsibilidade; evita corromper análise já submetida por aba antiga aberta | IA |
| D29 | Sorteio de revisores com `random.shuffle` em memória | `ORDER BY RANDOM()` | listas curtas; evita custo no SQL | IA |
| D30 | Revisão parcial nunca persistida: ou todos os revisores, ou nenhum + `fila_de_espera` | criar as que der | consistência do estado da revisão | IA |
| D31 | Notificações *best-effort* (`fail_silently=True`) | falhar a operação | e-mail não pode derrubar publicação | IA |
| D32 | `Q_CLUSTER.sync=True` em dev/test | worker obrigatório | mesma codebase roda com e sem worker | IA |

### 4.3. Decisões de escopo formalizadas na especificação

| ID | Decisão | Por quê | Onde |
|---|---|---|---|
| D33 | **v2.2: API REST + Swagger removidos do escopo** e a Fase 6 reescopada para saúde de links, dashboard e **JSON-LD (schema.org)** | "sem cliente real identificado, o custo de manutenção não se justifica"; JSON-LD torna o acervo *machine-readable* sem endpoints novos | `ESPECIFICACAO.md` §14 e Histórico de versões |
| D34 | Busca semântica (Fase 8) entra como **camada complementar opcional**, com toggle textual/semântico explícito | não substituir a busca textual, permitir comparação | v2.1 |
| D35 | Modelo `paraphrase-multilingual-MiniLM-L12-v2` (384-d) **em vez de `bge-m3`** (1024-d) | o servidor tinha ~1,2 GB livres; o bge-m3 exige 3–4 GB — **restrição física ditando arquitetura** | relatório fase-8 |
| D36 | FastAPI + `sentence-transformers` em vez de `text-embeddings-inference` | TEI é otimizado para GPU/alto volume; aqui é CPU e baixo tráfego | relatório fase-8 |
| D37 | Embeddings **fora** do histórico (`simple_history`) e serviço em *profile* separado | dado derivado e regenerável; ~1,5 KB por alteração sem valor de auditoria | relatório fase-8 |

### 4.4. Redesign imediato (30/04 – 01/05)

| ID | Decisão | Por quê |
|---|---|---|
| D38 | **Design system editorial** aplicado a todas as páginas públicas, um dia após o deploy | decisão estética do usuário; gerou `docs/especificacao/frontend.md` e mockups em `design_handoff_anco/` |
| D39 | Vitrine como home; planilha pública filtrável (Tabulator.js) em `/acervo/planilha/` | o público-alvo já trabalhava em planilha — a plataforma passou a **oferecer a planilha como saída**, em vez de negá-la |
| D40 | Lookup Crossref/ISBN no cadastro de artigo (`feat/analista-ux-crossref`) | eliminar digitação de metadados pelo analista |

---

## 5. Era 2 — O confronto com o uso real (03/06 – 08/06)

Cinco semanas de silêncio e o projeto volta com **165 commits em 6 dias**. É a
era das **reversões**: quase tudo que muda aqui desfaz uma decisão da Era 1 —
não por erro de implementação, mas porque o uso real revelou outro problema.

### 5.1. A primeira grande reversão: peer review → curadoria

| ID | Decisão (03/06) | O que substituiu | Por quê | Quem |
|---|---|---|---|---|
| D41 | **Análises não passam mais por revisão por pares**: `rascunho → submetida → (curador aprova) publicada` | o fluxo original (2 revisores estruturais + 2 cegos, publicação automática por consenso), Fase 4 inteira | pedido de produto; o ritual de revisão dupla era fricção excessiva para o perfil real dos participantes | C |
| D42 | **A revisão cega sobrevive só para a resenha crítica**, agora entidade própria (`Resenha`, 1:1 com `Analise`) | descartar o mecanismo | preserva o investimento da Fase 4 onde ele faz sentido (conteúdo autoral) | U←IA |
| D43 | O desvio é registrado como **addendum na especificação**, não como reescrita | editar as seções 5.3–5.6 | mantém legível o que era antes e por que mudou | U←IA |
| D44 | Cadastro aberto (qualquer conta Google entra como leitor; promoção a analista pela curadoria) | allowlist de domínio institucional | ampliar a entrada sem abrir a escrita | C |
| D45 | **Acervo legado é somente-leitura para analistas** (403 em `iniciar_analise`/`editar_*`) | permitir reanálise | o legado é pré-validado e isento de re-análise | E |

### 5.2. A triagem: da ferramenta externa ao app nativo

Antes de escrever código, o usuário pediu um **parecer de viabilidade** sobre
integrar um sistema de triagem existente (Streamlit) à plataforma
(`PARECER_integracao_triagem_ANCO.md`). O parecer ofereceu três opções
(A: importador leve; B: app nativo; C: fusão — "não recomendada") e recomendou
começar por A. **A decisão do usuário foi ir direto ao B.**

| ID | Decisão (04/06) | Alternativa | Por quê | Quem |
|---|---|---|---|---|
| D46 | **App nativo `apps/triagem`**, não importador da ferramenta externa | opção A do parecer | recorrência prevista do fluxo; stack divergente do Streamlit era o principal atrito | U |
| D47 | Ingestão por **arquivos** exportados (RIS/BibTeX/CSV), não por API das bases | integração por API | as bases relevantes não expõem API utilizável; documentado o uso do Zotero como ponte | U←IA |
| D48 | **Tabela separada** para candidatos (`RegistroTriagem`); só os **incluídos** viram `Artigo` | triar dentro do acervo | mantém o acervo curado intocado (contrato D57) | U |
| D49 | **Legado isento de triagem** no modo AnCo (`ja_no_acervo`) | triar tudo | não re-analisar o que já foi curado | E |
| D50 | Deduplicação **em camadas**: chave exata (UT do WoS) → título normalizado + ano → **embedding semântico** no resíduo | DOI como chave | o DOI do acervo é comprovadamente não confiável (D58); teste 80×80: duplicatas reais mediana cos 0,86 vs. 0,27 para mesmo-tema | U←IA |
| D51 | A camada semântica é **geradora de candidatos, nunca juíza** de identidade (≥0,80 quase-certa, 0,55–0,80 revisão humana) | decisão automática | "mede assunto, não obra" | U←IA |

### 5.3. Rigor metodológico (Fase 11) — construído e depois desligado

| ID | Decisão | Por quê |
|---|---|---|
| D52 | **κ de Fleiss**, não Cohen | os pares de revisores variam por registro (sorteio aleatório): nº fixo de avaliadores, avaliadores diferentes |
| D53 | Gate de calibração em **κ ≥ 0,60** (Landis & Koch), exibido ao curador que decide | limiar usual; a decisão continua humana |
| D54 | Triagem em duas etapas (título/resumo → texto completo) **opt-in** por flag, default `False` | preserva 100% do comportamento existente |
| D55 | Protocolo *a priori* com registro externo (OSF), versão e **trava** por `SnapshotProtocolo` | exigência do PRISMA-ScR |
| D56 | Calibração reusa `DecisaoTriagem` com etapa própria | "menos superfície" que um modelo paralelo |

### 5.4. Os contratos de dados que não se negociam

| ID | Decisão | Por quê | Quem |
|---|---|---|---|
| D57 | **O acervo curado é intocável.** Toda mudança em dado curado é **proposta** (`.md`/`.csv` paralelos), nunca aplicada sem confirmação | o acervo de fundação (653 registros) passou pela curadoria bibliográfica da Dra. Eneida Santana | E |
| D58 | **DOI não é chave de identidade** neste acervo: 68 de 311 DOIs auditados contra o Crossref estavam errados | um processo automático de recuperação anterior atribuiu DOIs de outros artigos | E |
| D59 | Correção aplicada em produção só **com aval da curadora**: 47 corrigidos, **21 esvaziados** (errado sem substituto confiável), `pg_dump` antes | esvaziar é preferível a manter um DOI que aponta para outro artigo | E |
| D60 | Auditoria dos vocabulários (`foco`, `epistemologia`): hapax 89%/70%, ruído sentinela, mistura de níveis → **camada de vocabulário controlado** que mapeia sem sobrescrever | "não exige tocar no acervo curado" | U←IA |

### 5.5. A segunda grande reversão: PRISMA rigoroso → "Revisão ANCO"

| ID | Decisão (05/06) | Por quê | Quem |
|---|---|---|---|
| D61 | **Adiar o PRISMA-ScR rigoroso** (Fases 9–12, recém-entregues) e adotar um fluxo simplificado para validação parcial da plataforma | "participantes atuais se comportam como alunos que querem nota"; revisão dupla cega, κ e calibração são fricção excessiva **neste momento** | C |
| D62 | Implementar como **modo aditivo por projeto** (`ProtocoloTriagem.modo ∈ {rigoroso, anco}`), não como remoção | "o rigoroso não é apagado — será usado depois, por quem quiser pesquisar de fato" | U←IA |
| D63 | Relevância por **correspondência de termos**, sem embeddings | a coordenação retirou o pré-requisito de embeddings em 05/06 | C |
| D64 | Sorteio de análise com **cota de 5 artigos/analista**, diversidade de base como **preferência, não regra dura** | evitar que a regra dura bloqueie o sorteio | C |
| D65 | O **curador** decide única/dupla e concilia a revisão dupla (`ConsensoAnalise`) | a conciliação é ato de curadoria, não de algoritmo | C |
| D66 | Autotriagem aceita só **incluir/excluir** (sem "dúvida") | "dúvida" criaria desempate onde só há um revisor | C |
| D67 | O parecer que embasou tudo isso recomendou **"NÃO implementar ainda"** até fechar 4 decisões de produto e validar 1 premissa; as decisões foram tomadas e travadas em 05/06, e só então veio o código | separação explícita entre "decisão da coordenação" e "decisão do implementador" | U←IA |

### 5.6. A terceira reversão, três dias depois (08/06)

| ID | Decisão | Por quê | Quem |
|---|---|---|---|
| D68 | **O modo ANCO deixa de ter triagem.** Todo registro novo importado entra direto no corpus | decisão da professora | C |
| D69 | **Redefinir o modo existente** em vez de criar um terceiro modo | evitar proliferação de modos | U←IA |
| D70 | A migração **reinclui as exclusões antigas** da autotriagem (as exclusões viram obsoletas); legado nunca tocado | decisão explícita do usuário | U |
| D71 | Inclusão automática **sem revisor fictício**: não cria `DecisaoTriagem`, `decidida_por = None` | auditável como inclusão automática, sem falsear autoria de decisão | IA |
| D72 | Sorteio **aleatório puro com semente gravada** (`SorteioAnalise.semente`) | reprodutibilidade e auditoria — "não nondeterminismo opaco" | IA |
| D73 | Todos os tipos de documento entram (artigo, tese, etc.) | o recorte deixou de ser feito na triagem | C |

### 5.7. A IA auditando o próprio trabalho (07/06)

| ID | Decisão | Resultado |
|---|---|---|
| D74 | Pedir à IA uma **auditoria técnica crítica** da plataforma que ela mesma construiu | veredito **8/10**, com 2 achados ALTA, 6 MÉDIA, 6 BAIXA |
| D75 | Corrigir os dois ALTA no mesmo dia: **CI rodando sem a extensão pgvector** que a migração exige, e **build não reprodutível** | `pgvector/pgvector:pg16` no CI; `requirements.lock` |
| D76 | Aceitar como dívida consciente a **duplicação intencional triagem↔acervo (~650 linhas)** | "espelha, não generaliza" — a generalização prematura era o risco maior |
| D77 | Avaliar a busca semântica com um **bloco de fronteira específico do domínio** ("viés de canonicidade AnCo"): 15 queries, 2 modos, colunas mecânicas preenchidas automaticamente e julgamento humano separado | método explicitamente desenhado para **não deixar a IA avaliar a si mesma** nos itens de juízo |

---

## 6. Era 3 — A separação estrutural (14/06 – 17/06)

| ID | Decisão | Por quê | Quem |
|---|---|---|---|
| D78 | **ANCO e PRISMA-ScR viram módulos completamente separados** (`apps/anco` × `apps/triagem`) | "objetivos antagônicos": ANCO é permissiva, multirreferencial, sem apego a protocolo; PRISMA busca rigor reconhecido internacionalmente. "Nasceram juntos só porque, na época, o significado de cada um não estava claro" | U |
| D79 | Critério de corte: PRISMA = pipeline de triagem; ANCO = import → corpus → sorteio → análise. **O acervo permanece compartilhado** | o acervo é destino comum, não mistura | U←IA |
| D80 | Executar em **5 fases com gate por fase** (0 inventário → A módulo novo atrás de flag → B corte de tráfego com redirect 301 → C limpeza destrutiva → D acesso por módulo → E documentação) | mesma disciplina faseada da Era 1 aplicada a uma refatoração | U←IA |
| D81 | A Fase A **duplica o código** (parsers, dedup) em vez de compartilhar | isolamento real: "mexer/quebrar um não afeta o outro" — dívida aceita conscientemente | U |
| D82 | Fase C **destrutiva com backup**: remove `modo`, `relevancia_score` e os models de sorteio/consenso do `apps/triagem` | o `relevancia_score` era calculado e gravado mas **nunca lido** no PRISMA — impacto funcional zero | U←IA |
| D83 | Acesso por módulo **global e por usuário** (`PRISMA_ATIVO`/`ANCO_ATIVO` + `User.pode_prisma`/`pode_anco`) | objetivo declarado do usuário: escolher quais módulos ficam ativos | U |
| D84 | **A relevância do PRISMA sai da plataforma**: virá do **ASReview** (active learning), integrado como **serviço ao lado** (abordagem A) | usar ferramenta open-source mantida upstream em vez de reimplementar; "valor rápido, baixo risco" | U←IA |
| D85 | Não criar o campo `prioridade_asreview` agora | "evita campo morto" — criar no momento da integração | IA |
| D86 | Ponto de extensão já escrito no código (`apps/triagem/asreview.py`, `NotImplementedError` com a nota da abordagem) | marca a costura sem implementar especulativamente | IA |
| D87 | ASReview fixado em **v2.2** (não `latest`/v3), publicado só em `127.0.0.1:9091`, acesso por túnel SSH | achado do piloto; o LAB não tem login — não publicar sem auth | U←IA |
| D88 | **Convenção de portas por milhar** (anco = 9000: web 9090, asreview 9091) | evitar colisão entre os vários projetos do mesmo servidor | U |
| D89 | Regra metodológica: no PRISMA **todo registro é triado, inclusive o que já está no acervo**; a isenção `ja_no_acervo` vale só no modo ANCO | isentar falsearia o fluxograma PRISMA | U |
| D90 | **Decisão metodológica deixada em aberto para a coordenação**: 1 revisor assistido por active learning **vs.** 2 revisores independentes | define o desenho do estudo, não é decisão de implementação | pendente (C) |

---

## 7. Era 4 — Fidelidade conceitual e uso real (02/07 – 08/07)

### 7.1. A plataforma reencontra a teoria de Fróes Burnham

O usuário pediu à IA um **parecer cotejando a plataforma com os dois capítulos
originais** de Teresinha Fróes Burnham (`PARECER_plataforma_x_proposta_Froes.md`).

| ID | Decisão | Por quê | Quem |
|---|---|---|---|
| D91 | **`area` (CAPES) e "área de significação" (Fróes) são dimensões irredutíveis** e devem coexistir, nunca ser fundidas num campo | tratar CAPES como a classificação do campo "contraria a tese central de Fróes" (a AnCo é multirreferencial e escapa das áreas disciplinares) | U←IA |
| D92 | Substituir a "Grande área CAPES" por **"Área de conhecimento"** no editor (08/06), revertendo a decisão de 03/06 que adotara o menu CNPq/CAPES | alinhamento conceitual | C |
| D93 | **Facetação da Epistemologia** (paradigma × método × disciplina) — aditiva e **reversível por comando** | os 106 termos eram um "balaio"; a faceta organiza sem apagar | U←IA |
| D94 | Corrigir o Protocolo AnCo para **não** usar a dicotomia binária "sentido estreito × amplo" | Fróes fala em dispersão/polissemia e campo emergente; o binário "arriscaria excluir obras que ela incluiria" | U←IA |
| D95 | Os limites da Matriz viram **proposta formal de 5 eixos** (espiral do conhecimento, tradução, comunidades, dimensões mobilizadas, compromisso ético-político), aditivos e opcionais — **nada implementado**, aguardando as coordenadoras | a Matriz é objeto de decisão acadêmica, não de produto | U←IA (pendente C) |

### 7.2. O tutorial das professoras como fonte normativa

| ID | Decisão (08/07) | Tensão registrada |
|---|---|---|
| D96 | **Realinhar o editor ao tutorial das professoras** (`orientacoes-analise.md`): ordem das abas, numeração dos itens, "Estrutura do artigo", Resultados antes de Referenciais | o tutorial passa a ser fonte normativa acima do desenho anterior |
| D97 | Registrar explicitamente que **dois textos entraram sem confirmação das professoras** — a área "conforme o periódico" e o critério restritivo de pertinência 6.1 | o critério do tutorial **está em tensão com a fidelidade a Fróes** (D94): o inclusivo "mesmo que não use o termo" foi substituído pelo restritivo. Marcado como "revert barato" |
| D98 | **Contexto de produção (4.3.2) obrigatório na submissão**, embora o tutorial o marque "Opcional" | decisão do usuário contra a letra do tutorial |

### 7.3. UX do analista — o que o uso real exigiu

Precedido de uma **investigação de usabilidade ponta a ponta** encomendada à IA
(`INVESTIGACAO_usabilidade_fluxo_ANCO.md`, 10 prioridades) e do relatório do que
foi aplicado (`RELATORIO_melhorias_aplicadas.md`).

| ID | Decisão | Por quê |
|---|---|---|
| D99 | Painel `/painel/` passa a ser **100% ANCO**; PRISMA vive em `/triagem/` | consequência da separação (D78) na navegação |
| D100 | **Worklist dedicada** "Sua análise cognitiva": só os artigos sorteados do analista, **sem filtros** | "à prova de troca-de-filtro" — o analista se perdia escolhendo escopo |
| D101 | **Sorteio = acompanhamento** (tela unificada com progresso por analista); a tela densa de acompanhamento é aposentada por redirect | duas telas para a mesma pergunta |
| D102 | Acesso à fila de curadoria exige papel **curador global** (não curador só-de-projeto) → duas professoras promovidas | a UI prometia acesso que o servidor negava com 403 |
| D103 | **Editor de análise em página única com abas client-side** | escolha explícita do estrutural sobre o remendo de "salvar ao interceptar clique" (D12) |
| D104 | Auto-save parcial deixa de apagar campos das outras abas; prazos e autosave em **hora local** | bugs de perda de trabalho relatados no uso real |
| D105 | Backfills de metadados via **OpenAlex + Crossref** (resumos truncados, palavras-chave vazias) — **aplica no não-legado, apenas propõe no legado** | contrato D57 respeitado por comando |
| D106 | Sorteio prioriza **diversidade de base por analista** e filtra por completude (tipo de documento e resumo presentes) | qualidade do lote sorteado |
| D107 | Sorteio **complementar** para novos analistas direto da UI | a equipe cresce depois do sorteio inicial |
| D108 | Curador pode **despublicar e devolver** análise aprovada por engano | válvula de reversão para erro humano da curadoria |
| D109 | **Tipo de acesso** classificado pelo analista (aberto / Portal CAPES / pago sem CAPES), visível também no acervo público | artigos importados em lote chegam sem essa informação |

---

## 8. Métricas

### 8.1. Produção de código

| Métrica | Valor |
|---|---|
| Commits | **332** (29/04 – 08/07/2026), 16 dias efetivos |
| Autoria dos commits | 277 `root` + 53 `Paulo Vicente` + 2 `Claude` — **todos** com trailer de co-autoria da IA |
| Linhas adicionadas / removidas (tudo) | 194.250 / 13.937 |
| Linhas `.py` + `.html` por era | Era 1: 17.193 · Era 2: 25.408 · Era 3: 6.331 · Era 4: 7.775 |
| Python de aplicação (sem migrations) | **30.838 linhas** |
| Templates | 90 arquivos, 8.495 linhas |
| Migrations | 59 |
| Testes | 80 arquivos, **731 funções de teste** |
| Distribuição por app | `acervo` 10.208 · `triagem` 8.820 · `anco` 6.149 · `core` 2.226 · `publico` 2.075 · `busca_semantica` 580 · `vocabulario` 216 |
| Tipos de commit | feat 176 · fix 61 · docs 40 · refactor 18 · chore 16 · style 13 · test 6 |
| Escopos mais frequentes | triagem 105 · acervo 59 · anco 38 · core 26 · publico 19 |

### 8.2. Modelos de IA usados (por trailer de co-autoria)

| Modelo | Commits | Período |
|---|---|---|
| Claude Opus 4.7 (1M) | 71 | 29/04 – 01/05 |
| Claude Sonnet 4.6 | 3 | 29/04 |
| Claude Opus 4.8 (1M) | 231 | 03/06 – 07/07 |
| Claude Opus 4.8 | 6 | 17/06 |
| Claude Fable 5 | 21 | 06/07 – 08/07 |

O projeto atravessou **três gerações de modelo** sem mudar o contrato de
processo (`CLAUDE.md`) — dado relevante para discutir estabilidade do método
diante da troca de ferramenta.

### 8.3. Uso real em produção (consulta em 03/09/2026)

| Métrica | Valor |
|---|---|
| Artigos | 1.459 (651 de acervo legado) |
| Análises | 730 — 651 legado, **51 submetidas**, 26 rascunho, 1 despublicada, 1 rejeitada |
| Usuários | 34 (24 analistas, 4 curadores, 6 leitores) |
| Módulo ANCO | 1 projeto, 26 membros, 31 fontes de importação, **998 itens de corpus**, 2 sorteios, **120 atribuições de análise** |
| Módulo PRISMA | 3 projetos, 5 buscas, 690 registros, 553 decisões de triagem |
| Vocabulário controlado | 753 termos |
| Serviços em produção | `web`, `worker`, `db` (pgvector/pg16), `cache`, `embeddings`, `asreview` v2.2 |

**Leitura:** o acervo de fundação (651) continua sendo a maior parte do
conteúdo público; o trabalho novo da comunidade está nas **51 análises
submetidas + 26 em rascunho** produzidas por 24 analistas a partir de 120
artigos sorteados. A plataforma saiu do protótipo, mas o volume novo ainda é
uma fração do legado — a validação está em curso.

---

## 9. Padrões recorrentes (o material analítico do artigo)

### P1. O ciclo em quatro tempos: parecer → decisão travada → fase → relatório

Nenhuma das grandes mudanças (triagem, modo ANCO, separação, Matriz de Fróes)
começou por código. Em todas, o usuário pediu primeiro um **parecer** à IA, com
opções e recomendação; a **coordenação decidiu**; as decisões foram **travadas
em documento datado**; só então veio a fase de implementação, encerrada por
relatório. Documentos-âncora: `PARECER_integracao_triagem_ANCO.md`,
`PARECER_triagem_simplificada_matriz_ANCO.md` (§0 "decisões da coordenação"),
`PARECER_plataforma_x_proposta_Froes.md`, `docs/planos/*.md` (§ "Decisões —
TRAVADAS").

### P2. A IA é autorizada a dizer "não implemente ainda"

O parecer de 04/06 recomendou explicitamente **"NÃO implementar ainda —
fechar 4 decisões de produto e validar 1 premissa; são decisões da coordenação,
não do implementador"**. Essa fronteira — *o que é decisão de produto/pesquisa
e o que é decisão de implementação* — foi mantida ao longo de todo o projeto e
é provavelmente o achado mais transferível da experiência.

### P3. Aditivo por padrão, destrutivo por exceção documentada

O padrão dominante é **flag/modo/faceta aditiva e reversível**: D54 (opt-in),
D62 (modo por projeto), D83 (acesso por módulo), D93 (facetação com comando de
desfazer), D95 (eixos opcionais). Houve **uma única migração destrutiva**
(D82), precedida de inventário, backup e da constatação de que o campo removido
nunca era lido. O custo desse padrão aparece no churn de 14/06: **3.808 linhas
removidas em um dia**.

### P4. Reversões não são erros de implementação — são aprendizado de domínio

Quatro reversões grandes, todas por decisão acadêmica após contato com o uso
real:

1. **Peer review de análises → curadoria** (03/06) — desfaz a Fase 4;
2. **PRISMA rigoroso → Revisão ANCO** (05/06) — desliga as Fases 9–12;
3. **Autotriagem → sem triagem** (08/06) — três dias depois da anterior;
4. **Modo dentro de um app → dois módulos separados** (14/06) — "nasceram
   juntos só porque o significado de cada um não estava claro".

A frase acima é a tese do artigo em uma linha: **a velocidade da IA permitiu
construir antes de entender o domínio**, e o custo disso foi pago em
refatoração — mas pago com o domínio já compreendido, o que talvez não fosse
possível sem ter construído.

### P5. Restrições físicas e humanas moldaram a arquitetura mais que preferências técnicas

1,2 GB de RAM livres definiram o modelo de embeddings (D35); a inexistência de
API nas bases definiu a ingestão por arquivo (D47); o perfil dos participantes
("alunos que querem nota") desligou o rigor metodológico (D61); um erro de
metadado histórico proibiu o DOI como chave (D58); a UI que prometia acesso
negado pelo servidor forçou a promoção de duas curadoras (D102).

### P6. A memória externa como condição do trabalho episódico

16 dias de trabalho em 71, com hiatos de até cinco semanas. As 13 memórias
persistentes (cada uma com *Why* e *How to apply*), o `CLAUDE.md`, os relatórios
de fase e o `docs/planos/RETOMAR.md` ("onde paramos") são o que permitiu
retomar sem reconstruir contexto. **A documentação deixou de ser subproduto e
virou infraestrutura de continuidade.**

### P7. A IA auditando o próprio trabalho — e os limites disso

A auditoria de 07/06 (D74) encontrou dois problemas ALTA reais e corrigíveis no
mesmo dia. Mas a avaliação da busca semântica (D77) foi deliberadamente
desenhada para separar **colunas mecânicas** (preenchidas automaticamente) de
**colunas de juízo** (humanas) — reconhecimento explícito de que a IA não
deveria julgar a relevância do que ela própria recuperou.

### P8. Governança de dados curados como cláusula pétrea

O contrato "o acervo de fundação é intocável" (D57) atravessou todas as eras e
converteu-se em código: 403 para analistas no legado (D45), isenção de triagem
(D49), backfills que *propõem* em vez de aplicar (D105), correção de DOI só com
aval e com `pg_dump` antes (D59). É o exemplo mais nítido de **autoridade
humana codificada como restrição de sistema**.

---

## 10. Lacunas de evidência e o que instrumentar daqui em diante

Para um relato de experiência metodologicamente sólido, o que **falta** medir —
e que só pode ser coletado a partir de agora:

| Lacuna | Por que importa | Como coletar |
|---|---|---|
| Transcrições das sessões | não há como medir prompts, retrabalho intra-sessão, correções de rumo | preservar `~/.claude/projects/**/**.jsonl` (hoje só a sessão corrente sobrevive) |
| Tempo por fase | as "estimativas em dias" do ROADMAP nunca foram confrontadas com o real | registrar início/fim de sessão no relatório de fase |
| Taxa de aceitação | quanto do que a IA propôs foi aceito, ajustado ou rejeitado | campo no relatório de fase: propostas × decisões |
| Defeitos por origem | quais bugs vieram de mal-entendido de domínio × erro de implementação | rotular commits `fix` com a causa |
| Percepção dos analistas | 24 analistas usam a plataforma; não há survey | questionário curto ao fim do ciclo atual |
| Verificação humana | quanto código foi lido linha a linha pelo usuário antes do merge | declarar no relatório |

---

## 11. Ganchos para o artigo

Cinco recortes possíveis, todos sustentados por evidência já levantada:

1. **"O contrato antes do código"** — `CLAUDE.md` como artefato de governança de
   agente: faseamento, parada obrigatória, relatório com seção de *desvios*,
   regra de quando perguntar. Evidências: D01–D12, os 25 relatórios de fase.
2. **"Construir para descobrir o domínio"** — as quatro reversões (P4) e o custo
   medido em churn: a IA permitiu prototipar o rigor metodológico completo
   (κ, calibração, PRISMA) e **descobrir que ele não cabia** naquele grupo.
3. **"Quem decide o quê"** — a fronteira entre decisão de coordenação
   acadêmica, curadoria bibliográfica e implementação; o parecer que diz "não
   implemente ainda" (P2); a Matriz de Fróes proposta e não implementada (D95).
4. **"Dado curado como cláusula pétrea"** — o contrato da Dra. Eneida traduzido
   em restrições de código (P8), e o caso do DOI (D58/D59) como exemplo de
   limite do automatismo.
5. **"Trabalho episódico e memória externa"** — 16 dias em 71, três gerações de
   modelo, mesmo contrato de processo (P6, §8.2).

---

## 12. Índice de evidências (caminhos)

```
Repositório: /home/anco-paulovicente/htdocs/anco.paulovicente.pro.br
  CLAUDE.md                                  contrato de processo com o agente
  docs/especificacao/ESPECIFICACAO.md                      v2.2 + Histórico de versões + 3 addenda
  docs/ROADMAP.md                            estado vivo das fases
  docs/relatorios/fase-{0..14}.md            25 relatórios de fim de fase
  docs/relatorios/separacao-anco-prisma-*.md relatórios da refatoração (Fases 0,A,B,C,D)
  docs/planos/{fase-12,fase-13}.md           decisões travadas antes de implementar
  docs/planos/separacao-anco-prisma.md       plano da separação em 5 fases com gates
  docs/planos/integracao-asreview.md         opções A/B + achados do piloto
  docs/planos/RETOMAR.md                     ponto de retomada (14/06)
  docs/relatorios/auditoria-tecnica-2026-06.md          autoavaliação crítica (8/10)
  docs/busca_semantica/avaliacao.md          protocolo de avaliação com bloco de fronteira
  docs/metodo/proposta-evolucao-matriz-froes.md     5 eixos, aguardando coordenadoras
  docs/metodo/protocolo-anco-analise.md             guia das abas, corrigido por fidelidade a Fróes
  docs/metodo/facetacao-epistemologia-froes.md      facetação reversível do vocabulário
  docs/migracao/{analise_legado,auditoria_qualidade,problemas_base_revisada}.md
  orientacoes-analise.md                     tutorial das professoras (fonte normativa, jul/2026)

Diretório de trabalho: /home/anco-paulovicente
  PARECER_integracao_triagem_ANCO.md         viabilidade da triagem (opções A/B/C)
  PARECER_triagem_simplificada_matriz_ANCO.md  §0 = decisões da coordenação (05/06)
  PARECER_plataforma_x_proposta_Froes.md     cotejo com os capítulos originais
  INVESTIGACAO_usabilidade_fluxo_ANCO.md     10 prioridades de usabilidade
  RELATORIO_melhorias_aplicadas.md           o que foi aplicado e o que ficou de fora
  Analise-Cognitiva/                         capítulos originais de Fróes Burnham

Memória persistente do agente
  /root/.claude/projects/-home-anco-paulovicente/memory/*.md          13 memórias (atual)
  /root/.claude/projects/-home-anco-paulovicente-htdocs-.../memory/   4 memórias (abr/2026)
```
