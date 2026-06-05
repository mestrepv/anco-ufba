# Plano — Fase 13: Revisão ANCO (modo simplificado de triagem + sorteio de análise)

> **Status:** proposta para aprovação humana. **Nenhum código foi escrito.**
> **Data:** 2026-06-05 · **Base de decisão:** `PARECER_triagem_simplificada_matriz_ANCO.md` (§0, v2).
>
> **Princípio inegociável:** esta fase é **aditiva e não-destrutiva**. O protocolo
> **PRISMA-ScR rigoroso (Fases 9–12) permanece intacto**; o acervo curado (653
> registros) permanece **somente-leitura**. Tudo aqui vive atrás de um **modo por
> projeto** — nada do que existe é removido.

---

## 1. Objetivo

Automatizar, na plataforma, o fluxo **como já se faz na disciplina Análise
Cognitiva** (Profas. Teresinha Fróes e Leliana): triagem leve pelo próprio dono
da base, lista curta ordenada por relevância, e distribuição de uma **cota de 5
artigos por analista** para análise pela Matriz AnCo — com opção de **revisão
única ou dupla**. Meta de UX: **não assustar** o analista com a pilha grande;
ele vê pouco, ordenado, e recebe uma cota fixa.

---

## 2. Modelo de dados (alterações aditivas)

### 2.1. `ProtocoloTriagem` — campo de modo
```python
class Modo(models.TextChoices):
    RIGOROSO = "rigoroso", "Rigoroso (PRISMA-ScR)"
    ANCO = "anco", "Revisão ANCO (simplificado)"
modo = models.CharField(max_length=10, choices=Modo.choices, default=Modo.RIGOROSO)
```
- `default=RIGOROSO` ⇒ **projetos existentes não mudam de comportamento**.
- `modo=ANCO` ativa: autotriagem (§3.1), oculta κ/checklist/calibração/2-etapas
  na UI, e habilita o sorteio-de-análise (§3.4). **Nada disso apaga o código
  rigoroso** — são ramos guardados pelo modo.

### 2.2. `RegistroTriagem.relevancia_score` (cache de ordenação)
```python
relevancia_score = models.PositiveSmallIntegerField(default=0, db_index=True)
```
Recalculado na consolidação da triagem (§3.3). Cache do cálculo da §3.3 — pode
ser regerado por management command a qualquer momento; não é fonte de verdade.

### 2.3. Sorteio-de-análise (novos modelos)
```python
class SorteioAnalise(models.Model):
    projeto       = FK(ProtocoloTriagem, related_name="sorteios_analise")
    modo_revisao  = CharField(choices=[("unica","Revisão única"),
                                       ("dupla","Revisão dupla (2 + consenso)")])
    cota          = PositiveSmallIntegerField(default=5)
    criado_por    = FK(User)           # professora / curador
    criado_em     = DateTimeField(auto_now_add=True)
    observacoes   = TextField(blank=True)

class AtribuicaoAnalise(models.Model):
    sorteio   = FK(SorteioAnalise, related_name="atribuicoes")
    analista  = FK(User, related_name="atribuicoes_analise")
    artigo    = FK("acervo.Artigo", related_name="atribuicoes")
    criado_em = DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [UniqueConstraint(fields=["sorteio","analista","artigo"], ...)]
```

### 2.4. Consenso da revisão dupla
Estruturalmente o acervo **já permite N análises por artigo** (cada analista
analisa uma vez). Falta só a conciliação. Proposta mínima:
```python
class ConsensoAnalise(models.Model):
    artigo        = FK("acervo.Artigo")
    sorteio       = FK(SorteioAnalise, null=True)
    analises      = M2M("acervo.Analise", related_name="+")   # as 2 independentes
    analise_final = FK("acervo.Analise", null=True, related_name="consenso")
    conciliado_por= FK(User, null=True)                       # default: curador
    conciliado_em = DateTimeField(null=True)
```
*(Decisão a confirmar — §8: quem concilia. Default = curador, encaixa na
curadoria `submetida → curador aprova` já existente.)*

**Migrations:** `triagem 0020` (modo, relevancia_score, SorteioAnalise,
AtribuicaoAnalise, ConsensoAnalise). Sem alteração de schema no acervo curado.

---

## 3. Fluxo

### 3.1. Autotriagem (R2) — o dono tria a própria base
- Em `modo=ANCO`, o importador tria **seus próprios** registros (gate idêntico
  ao da dedup: `user.id in importadores(registro)` — espelha
  `duplicatas.importadores` / `pares_do_usuario`).
- Ação "incluir/excluir/dúvida" cria **uma** `DecisaoTriagem` (etapa `ta`) já
  concluída para o importador e chama `aprovacao.avaliar_apos_triagem`, que
  **consolida com um único parecer** (todo-incluir → `incluido`; todo-excluir →
  `excluido`) — **reusa a lógica existente** ([aprovacao.py:124](../../apps/triagem/aprovacao.py)).
- **Não passa pelo `executar_sorteio`** (que exclui o importador por
  independência) — esse caminho fica reservado ao `modo=RIGOROSO`.
- Proveniência: `decidida_por = importador`; `HistoricalRecords` registra
  "autotriagem". Permite re-triagem rigorosa futura (outro projeto, `modo=RIGOROSO`).

### 3.2. Dedup (já pronto, sem código novo)
`pares_do_usuario` já entrega ao analista os pares da sua base **e** os
cruzamentos com outras bases ([duplicatas.py:112](../../apps/triagem/duplicatas.py)).
Acervo intocável: `ja_no_acervo` não re-tria.

### 3.3. Relevância (R3) — correspondência de termos, **sem embeddings**
```
relevancia_score(registro) = nº de termos distintos da estratégia de busca
   (ProtocoloTriagem.termos_realce, fallback tokens de string_busca/estrategia_busca)
   presentes em  unaccent(lower(titulo ++ resumo ++ palavras_chaves))
```
- Calculado na consolidação (§3.1) e cacheado em `relevancia_score`.
- Management command `recalcular_relevancia <projeto>` para reprocessar.
- Tela `/triagem/p/<slug>/incluidos/`: pool de **incluídos ordenado por
  `-relevancia_score, -ano`**, com badge "casou com N termos" (explicável).

### 3.4. Sorteio-de-análise (R4 + R5) — cota 5, bases diferentes, única/dupla
Entrada (curador/professora): `modo_revisao ∈ {unica, dupla}`, `cota=5`.

Algoritmo (guloso, determinístico salvo o desempate aleatório):
1. **Pool** = `Artigo` incluídos do projeto ainda não atribuídos neste sorteio,
   ordenados por `-relevancia_score`.
2. **Analistas** = membros analistas do projeto.
3. **Assentos por artigo** = 1 (`unica`) ou 2 (`dupla`).
4. Round-robin entre analistas; para cada um, escolher o próximo artigo de
   **maior relevância cuja base ainda não esteja no conjunto daquele analista**
   (diversidade de base como **preferência**). Se não houver artigo de base nova,
   pega o de maior relevância restante — **a diversidade nunca bloqueia a cota**
   (decisão §8.2).
5. Nunca atribuir a um analista um artigo que ele já analisou; em `dupla`, os 2
   analistas do artigo são distintos (e, idealmente, nenhum é o importador da base).
6. Pára quando cada analista tem `cota=5` **ou** o pool esgota. **Faltas são
   logadas** (espelha o padrão "fila de espera" do sorteio de triagem) — nada de
   truncamento silencioso.

Resultado: `AtribuicaoAnalise` por (analista, artigo).

### 3.5. Análise e (se dupla) consenso
- `a_analisar` (R-A): em `modo=ANCO` **com sorteio**, o analista vê **apenas seus
  artigos atribuídos** (não mais o self-service de todos os incluídos —
  [views.py:755](../../apps/triagem/views.py)).
- `unica`: 1 `Analise` por artigo → fluxo de curadoria atual.
- `dupla`: 2 `Analise` independentes → quando ambas `submetida`, abre
  `ConsensoAnalise` para o **curador** conciliar → `analise_final` publicada;
  as duas de origem ficam como insumo (não apagadas).

---

## 4. UI / rótulo (R1)
- Em `modo=ANCO`, todas as telas usam **"Revisão ANCO"**; **ocultam** painéis de
  κ/concordância, checklist PRISMA-ScR, calibração e protocolo-a-priori
  (condicionais por modo — o código continua lá para `modo=RIGOROSO`).
- A lista de projetos sinaliza o modo de cada projeto.

---

## 5. Telas / URLs (novas, sob o escopo de projeto da Fase 12)
- `/triagem/p/<slug>/incluidos/` — pool ordenado por relevância (curador/professora).
- `/triagem/p/<slug>/sorteio-analise/` — criar sorteio (modo única/dupla, cota), ver resultado.
- `/triagem/p/<slug>/consenso/` — fila de conciliação (curador), só `modo=dupla`.
- `a-analisar` (global) passa a respeitar atribuições quando o projeto é `modo=ANCO`.

---

## 6. Testes obrigatórios (CLAUDE.md §6)
- Autotriagem só pelo importador; consolida com 1 parecer; gate de outro usuário → 403.
- Relevância: ordenação por nº de termos; recálculo idempotente.
- Sorteio: cota=5; **nunca 5 da mesma base**; `dupla` ⇒ 2 analistas distintos;
  exclui quem já analisou; faltas logadas (pool insuficiente).
- Consenso: 2 análises → conciliação → `analise_final`; origens preservadas.
- **Regressão:** `modo=RIGOROSO` inalterado (sorteio independente exclui coletor,
  κ, calibração, 2 etapas, desempate) — suíte das Fases 9–12 verde.

---

## 7. Critérios de aceite
- [ ] Projeto `modo=ANCO`: importar base → deduplicar (próprias+cruzadas) →
  autotriar → ver incluídos por relevância → sortear 5/analista de bases
  diferentes → analista vê só os seus → (dupla) curador concilia.
- [ ] Projeto `modo=RIGOROSO` continua idêntico às Fases 9–12 (sem regressão).
- [ ] Acervo curado intocado; nenhuma migração destrutiva.
- [ ] Rótulos PRISMA/κ ausentes na UI do modo ANCO; presentes no rigoroso.
- [ ] Cobertura ≥70% nas linhas novas.

---

## 8. Decisões confirmadas (2026-06-05) — spec travado
1. **A relevância pondera o sorteio** (não só a lista): a alocação prioriza os
   incluídos de maior `relevancia_score`.
2. **Diversidade de base é preferência, não regra dura:** ideal 5 bases
   distintas, mas **não obrigatório** — o algoritmo maximiza distinção de bases
   e **nunca bloqueia** a cota por causa disso (cai para repetição de base se
   preciso).
3. **O curador decide única/dupla no momento do sorteio** (`SorteioAnalise.
   modo_revisao`), e **o curador concilia** a revisão dupla (§3.5).
4. **Consenso via `ConsensoAnalise`** (§2.4), modelo enxuto e aditivo.

---

## 9. Fora de escopo (preservado para depois)
- Relevância **semântica** por embeddings/base referencial (Fase 8) — adiada.
- Protocolo PRISMA-ScR como fluxo ativo dos analistas comuns — fica para projetos
  `modo=RIGOROSO`, sob demanda dos que quiserem publicar com rigor.
</content>
