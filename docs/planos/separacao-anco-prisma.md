# Plano — Separação ANCO × PRISMA-ScR em módulos independentes

> Status: **proposta, aguardando aprovação**. Decisão registrada: ANCO e
> PRISMA-ScR têm objetivos antagônicos e **não podem se misturar**. Hoje vivem
> sob `apps/triagem` com um campo `ProtocoloTriagem.modo` e ~25 ramificações
> `if eh_anco`. Vamos separá-los em dois módulos independentes.

## Princípios (decididos)

1. **Dois módulos independentes**, cada um com seus models, views, URLs,
   templates e navegação. **Zero `if eh_anco`.** Quebrar/mudar um não afeta o outro.
2. **Encanamento duplicado** (parsers RIS/BibTeX/CSV + algoritmo de dedup): cada
   módulo tem a sua cópia. Sem biblioteca compartilhada — independência total.
3. **PRISMA herda o `apps/triagem` atual** (a triagem É o PRISMA). O ANCO é
   **extraído** para um novo app.
4. **Acervo é o destino comum e global** (`apps/acervo`: Artigo/Análise) — os dois
   módulos promovem/analisam ali. Não é "misturar"; é a estante publicada.
5. **Ativação**: cada módulo pode ser ligado/desligado **globalmente** e o acesso
   é concedido **por usuário**.

## Mapa dos módulos

```
apps/
├── acervo/      GLOBAL, inalterado — Artigo, Analise, Resenha (destino dos dois)
├── triagem/     = MÓDULO PRISMA-ScR (após limpeza: só o rigoroso)
└── anco/        = MÓDULO ANCO (novo)
```

| Hoje em `apps/triagem` | Vai para |
|---|---|
| `ProtocoloTriagem` (sem `modo`), `ProjetoMembro`, `Busca`, `RegistroTriagem`, `DecisaoTriagem`, `ParDuplicataDescartado`, `RodadaCalibracao`, `SnapshotProtocolo` | **fica** (PRISMA) |
| checklist, concordância (κ), calibração, prisma (fluxograma), triagem_direta, sorteio de revisores, desempate | **fica** (PRISMA) |
| `SorteioAnalise`, `AtribuicaoAnalise`, `ConsensoAnalise` | **→ anco** |
| `autotriagem.py`, `sorteio_analise.py`, `relevancia.py`, branch `eh_anco` de `importacao`/`aprovacao`/`estatisticas` | **→ anco** |

---

## Fase 0 — Preparação e inventário

- [ ] Criar branch `refactor-separacao-anco-prisma` a partir de `main`.
- [ ] Inventariar projetos de produção por modo (`ProtocoloTriagem` por `modo`):
      slugs ANCO + contagens (projetos, fontes, itens de corpus, sorteios,
      consensos, análises vinculadas).
- [ ] Backup do banco (`pg_dump`) rotulado "pré-separação".
- [ ] Rodar a suíte e registrar o número verde como baseline.
- [ ] Escrever o "contrato de paridade": o que um projeto ANCO precisa fazer
      idêntico depois (importar, corpus, sorteio, consenso, analisar, estatística).

**Aceite:** inventário + backup prontos; baseline verde registrada.

## Fase A — Criar `apps/anco` (aditivo, atrás de flag)

Models
- [ ] `ProjetoANCO` (nome, slug, pergunta_pesquisa, estrategia_busca, arquivado, datas).
- [ ] `MembroANCO(projeto, usuario, papel∈{analista,curador})`.
- [ ] `FonteImport` (≈ `Busca`: base, arquivo, contagens, criado_por).
- [ ] `ItemCorpus` (≈ `RegistroTriagem` **sem estados de triagem**: metadados,
      origem, `artigo` FK, incluido_em/por; status `no_corpus`/`removido`).
- [ ] `SorteioAnalise`, `AtribuicaoAnalise`, `ConsensoAnalise` (espelhados).
- [ ] Migrations iniciais do app.

Encanamento (cópia própria — decisão: duplicar)
- [ ] `apps/anco/parsers.py` — cópia de `parse_ris/bibtex/csv` + `analisar_arquivo`.
- [ ] `apps/anco/dedup.py` — cópia da chave/similaridade de deduplicação.

Lógica
- [ ] `apps/anco/importacao.py` — importar → `ItemCorpus` direto no corpus
      (sem triagem), com dedup interno.
- [ ] `apps/anco/sorteio.py` — sorteio aleatório por cota (semente) + consenso da dupla.
- [ ] `apps/anco/estatisticas.py` — artigos × bases.
- [ ] Promoção/análise via `apps/acervo` (reusa `Analise`/`Artigo`; nunca toca o curado).

Views / URLs / templates
- [ ] `apps/anco/views.py` + `urls.py` montadas em `/anco/…`
      (painel, importar, corpus, sorteio, consenso, estatística, equipe).
- [ ] Templates próprios em `templates/anco/` (a partir do que hoje é ANCO).
- [ ] Comando `manage.py importar_anco`.

Migração de dados
- [ ] `manage.py migrar_anco` — copia projetos `modo=anco` (+ fontes, corpus,
      sorteios, consensos, vínculos de análise) para as tabelas novas.
      **Idempotente**, com `--dry-run` e `--projeto <slug>`; loga contagens
      antes/depois; **não toca o acervo**.

Flag e testes
- [ ] `anco_ativo` (settings/flag) default **OFF**; rotas/nav só sob a flag.
- [ ] `apps/anco/tests/` — import→corpus, sorteio, consenso, estatística e
      migração (dry-run e real).

**Aceite:** com a flag ON em local/staging, um projeto ANCO migrado faz tudo
idêntico ao atual; `migrar_anco --dry-run` bate contagens; suíte verde.
**`apps/triagem` permanece intocado.** → Relatório + aprovação.

## Fase B — Cortar o tráfego ANCO para o novo módulo

- [ ] Rodar `migrar_anco` real em produção (após backup).
- [ ] Ligar `anco_ativo` em produção.
- [ ] Redirect 301 de `/triagem/p/<slug>/…` (projetos `modo=anco`) → `/anco/p/<slug>/…`.
- [ ] Lista/navegação de projetos: ANCO aponta para o módulo novo.
- [ ] Curador valida 1 projeto ANCO real (paridade ponta a ponta).

**Aceite:** nenhum acesso ANCO cai no `apps/triagem`; URLs antigas redirecionam;
curador confirma paridade. → Relatório + aprovação.

## Fase C — Limpar `apps/triagem` (PRISMA puro)

- [ ] Remover models ANCO de triagem (`SorteioAnalise`/`AtribuicaoAnalise`/
      `ConsensoAnalise`) — migration de remoção (após confirmar zero leitura ANCO).
- [ ] Remover arquivos: `autotriagem.py`, `sorteio_analise.py`, `relevancia.py`.
- [ ] Podar branches `eh_anco` em `importacao.py`, `aprovacao.py`
      (`incluir_automaticamente`/`incluir_corpus_total`/`desfazer_autotriagem`),
      `estatisticas.py`.
- [ ] Remover views/rotas ANCO: `autotriar_view`, `sorteio_analise_view`,
      `consenso_view`, `incluir_corpus_view`.
- [ ] Remover campo `modo` e `eh_anco` de `ProtocoloTriagem` (migration).
- [ ] Limpar galhos `eh_anco` em `painel/incluidos/protocolo/projetos/ajuda.html`
      (`incluidos` vira só "Artigos incluídos").
- [ ] Mover/remover testes que usavam `proj_anco` dentro de `triagem`.

**Aceite:** `grep -ri "eh_anco\|\banco\b" apps/triagem` → zero; suíte PRISMA verde.
→ Relatório + aprovação.

## Fase D — Ativação global + por usuário

- [ ] `ModuloConfig` (`prisma_ativo`, `anco_ativo`) — singleton no admin (ou settings).
- [ ] Permissão por usuário `pode_prisma`/`pode_anco` (campos no User ou grupos)
      + ação em massa no `UserAdmin`.
- [ ] Navegação condicional: nav mostra só módulos ativos **e** permitidos ao usuário.
- [ ] Guard de rota: módulo desligado ou sem permissão → 404/redirect.
- [ ] Testes de ativação (global e por usuário).

**Aceite:** ligar/desligar cada módulo e conceder acesso por usuário funciona
ponta a ponta. → Relatório + aprovação.

## Fase E — Aposentar restos e documentar

- [ ] Remover código/migrations órfãos; `makemigrations --check` limpo.
- [ ] Atualizar `CLAUDE.md` (§9.2-bis e seguintes) e `docs/` para os dois módulos.
- [ ] Relatório final + nota: parsers/dedup duplicados → corrigir bug nos dois lugares.

**Aceite:** build limpo; docs coerentes.

---

## Riscos e mitigações

- **Migração de dados** é o ponto sensível → `--dry-run` obrigatório, backup, e
  conferência de contagens (projetos/itens/sorteios) antes e depois.
- **URLs citáveis**: caminhos `/triagem/p/<slug>/…` de projetos ANCO mudam de
  prefixo → redirects 301 dos antigos.
- **`apps/acervo`** compartilhado: mantido como está; só os módulos mudam.
- **Duplicação de parsers/dedup**: aceita por decisão; documentar que correções
  de bug precisam ir aos dois lugares.

## Gate de cada fase

Cada fase termina com **Relatório de Fim de Fase** (CLAUDE.md §7) e **aprovação
humana** antes da próxima. Trabalho na branch `refactor-separacao-anco-prisma`.
