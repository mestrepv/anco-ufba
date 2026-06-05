# Relatório — Fase 12: Projetos (múltiplas revisões de escopo)

Transforma a triagem mono-protocolo numa plataforma **multi-projeto**: cada projeto é
uma revisão de escopo independente (pergunta, estratégia, protocolo registrado, corpus,
dedup, PRISMA e κ próprios), com **equipe designada pelo admin**. Aditivo e seguro: o
esquema já carregava `protocolo` como FK em tudo; a evolução foi aposentar o singleton.

Plano e decisões travadas: `docs/planos/fase-12-projetos.md`.

## Sub-fases

| Sub-fase | Entrega | Status |
|---|---|---|
| **12.0** | `ProtocoloTriagem` ganha `nome/slug/estrategia_busca/arquivado` + helpers de membership; modelo `ProjetoMembro(projeto, usuario, papel)`. **Migração de dados** `0019`: protocolo atual → projeto **“Análise Cognitiva”** (slug `analise-cognitiva`), usuários ativos viram membros (2 curadores, 20 analistas). | ✅ |
| **12.1** | **Escopo por URL** `/triagem/p/<slug>/…`; `/triagem/` vira a **lista de projetos**; `ativo()` aposentado nas views (com **redirects de compat** dos caminhos antigos → projeto default). | ✅ |
| **12.2** | **Permissões por membership**: acesso às telas do projeto exige ser membro; ações de curador via `eh_curador_no` (papel no projeto **ou** `is_staff`); **sorteio e calibração restritos aos membros** do projeto. | ✅ |
| **12.3** | **UI**: lista de projetos, **criar projeto** (admin), seletor/“trocar projeto” no `/painel/`, designação de membros pelo **admin** (inline em ProtocoloTriagem + `ProjetoMembro`). | ✅ |
| **12.4** | **Gate de dedup por membership** (a regra adiada da Fase 11): curador resolve qualquer par; o analista vê/resolve só os pares que tocam **bases que ele importou**. | ✅ |
| **12.5** | Documentação, testes e deploy. | ✅ |

## Arquitetura resultante

- **`ProtocoloTriagem` = o projeto** (mantém a tabela; o `SnapshotProtocolo` já dá o
  versionamento interno). `slug` é gerado no `save()` (único). `ativo()` agora devolve o
  1º projeto não arquivado — usado só pelos redirects de compat e por código legado.
- **`ProjetoMembro(projeto, usuario, papel∈{analista,curador})`** — papel **por projeto**
  (alguém pode ser curador de um e analista de outro). O papel global de `User` continua
  governando o acesso à plataforma; a aprovação de revisor (`revisor_aprovado`) segue
  **global** e soma-se ao membership (dois filtros).
- **Escopo por URL**: rotas do projeto sob `p/<slug>/`; rotas globais por-usuário
  (`/triagem/`, `ajuda`, `minhas`, `triar/<id>`, `a-analisar`) sem slug. Decoradores
  `_projeto_analista` / `_projeto_curador` resolvem o projeto e aplicam o membership.
- **Global permanece global**: acervo (`Artigo`) e análise (Matriz AnCo), usuários,
  vocabulário/bases. O mesmo artigo pode ser incluído por dois projetos (reusa o mesmo
  `Artigo`, idempotente); a análise é uma só por artigo.

## Critério de aceite
- [x] N projetos, cada um com protocolo/PRISMA/κ isolados.
- [x] Admin designa membros e papéis por projeto.
- [x] Acesso e sorteio restritos aos membros do projeto.
- [x] Acervo/análise globais; legado intocado.
- [x] Gate de dedup por importador/curador (resolve a observação do “Analista de Teste”).
- [x] Caminhos antigos redirecionam (sem links quebrados durante a transição).

## Decisões de implementação
- **Elevar `ProtocoloTriagem` a projeto** em vez de criar um `Projeto` separado: menos
  migração, mesmo resultado; o snapshot já versiona.
- **URL-scoping** (não sessão): links compartilháveis, sem estado oculto. Custo: tocar
  todas as views/templates da triagem — feito com `slug` no contexto e helper de teste.
- **`eh_curador_no(user)`** = `is_staff` **ou** papel-no-projeto `curador`. O admin
  enxerga e gerencia todos os projetos.
- **Gate de dedup** baseado em `origem_buscas.criado_por` (quem importou). Na listagem, o
  analista vê só os pares que pode resolver; o curador vê todos. Ações verificam de novo
  no POST (defesa em profundidade).

## Desvios da especificação
Nenhum. Estende o addendum de triagem; sem alteração no schema de `acervo`/`Analise`.

## Dívida técnica deixada
- O `/painel/` mostra o **fluxo do 1º projeto** do usuário + “trocar projeto”; um seletor
  rico (status por projeto) pode vir depois.
- Concordância exibida é a do projeto corrente (1ª etapa). Multi-projeto não agrega κ
  entre projetos (correto: são revisões distintas).

## Métricas / verificação
- Migrations triagem `0018` (campos + `ProjetoMembro`), `0019` (dados: Projeto 1 + membros).
- Testes: suíte da triagem reescrita para o escopo por projeto (helper `turl`/`membro` em
  `tests/conftest.py`) + novos testes de projetos, membership e gate de dedup.
  **Suíte completa verde**; `ruff` limpo; `manage.py check` ok.
- **Render-smoke** autenticado de todas as telas (lista, projeto, protocolo, checklist,
  calibração, importar, registros, duplicatas, mescladas, iniciar, desempate, PRISMA,
  `/painel/`) → 200; redirects de compat OK.

## Pendências para o usuário (teste manual)
1. `/triagem/` — ver a lista de projetos; entrar em **Análise Cognitiva**.
2. **Admin → Protocolos de triagem → Análise Cognitiva**: conferir/ajustar **membros**.
3. (Opcional) **Novo projeto** com outra estratégia de busca; designar membros; importar
   uma base e checar que o corpus/PRISMA é isolado.
4. Confirmar o **gate de dedup**: um analista só vê duplicatas das bases que importou; o
   curador vê todas.
