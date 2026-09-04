# Plano de escrita — artigo de relato de experiência

> **Objeto do artigo.** O processo de modelagem e o teste de uso da Plataforma
> AnCo, desenvolvida em parceria com um agente de IA (Claude Code), entre
> 29/04 e 08/07/2026, com uso real observado até 03/09/2026.
>
> **Insumo.** `docs/artigo/inventario-de-decisoes.md` (inventário de
> 109 decisões D01–D109, 5 eras, 8 padrões P1–P8, 5 ganchos). Este plano
> converte esse inventário em um artigo; ele **não** repete o inventário.
>
> Plano produzido em 03/09/2026.

---

## 1. Decisões editoriais a fechar antes de escrever

O plano abaixo assume os itens da coluna "Assumido". Se algum mudar, os
orçamentos de palavras e a seção 4 mudam junto.

| Decisão | Assumido | Por que importa |
|---|---|---|
| Gênero | **Relato de experiência** (não estudo de caso, não artigo empírico) | libera de exigir hipótese e amostra; obriga a reflexão crítica e transferibilidade |
| Veículo | periódico/evento brasileiro de Educação, Informática na Educação ou Ciência da Informação, em pt-BR, 6.000–8.000 palavras | define ABNT × APA, limite de páginas, se aceita figuras coloridas |
| Autoria | usuário (1º autor) + coordenação acadêmica (Fróes, Leliana, Cláudia) + curadoria (Eneida) como coautoras ou como participantes nomeadas **com consentimento** | pessoas reais são citadas em decisões (D41, D57, D68); sem consentimento, anonimizar por papel ("coordenação", "curadoria") |
| Papel da IA no texto | ferramenta e **objeto** do relato; **não** coautora; declarar uso de IA na escrita do artigo conforme política do veículo | veículos exigem declaração; o artigo perde credibilidade se a IA que construiu, auditou e inventariou também julgar o resultado sem isso estar explícito |
| Tese central | **"Construir para descobrir o domínio"** (gancho 2) sustentada por **"o contrato antes do código"** (gancho 1) e **"quem decide o quê"** (gancho 3) | um artigo com 5 ganchos vira catálogo; três se encaixam como causa (contrato) → fenômeno (reversões) → condição (fronteira de decisão) |
| Ganchos 4 e 5 | subseções da Discussão, não eixos | "cláusula pétrea" (P8) e "memória externa" (P6) são evidência da tese, não teses próprias |
| Idioma | pt-BR; termos de código em inglês só quando necessário | público-alvo |

---

## 2. Tese e argumento em um parágrafo

A velocidade do agente de IA permitiu implantar em produção, em três dias,
uma plataforma completa com revisão por pares, protocolo PRISMA-ScR, κ de
Fleiss e calibração. O uso real por 24 analistas mostrou, em quatro reversões
sucessivas (peer review → curadoria; PRISMA rigoroso → Revisão ANCO;
autotriagem → sem triagem; um app com modos → dois módulos), que boa parte
desse rigor não cabia no grupo nem no conceito de Análise Cognitiva de Fróes
Burnham. O custo foi pago em refatoração, mas com o domínio já compreendido.
Isso só foi governável porque (a) um contrato de processo escrito antes do
código impôs fases, paradas e relatórios com seção de desvios; e (b) a
fronteira entre decisão de implementação, de coordenação acadêmica e de
curadoria foi mantida explícita, inclusive com a IA autorizada a recomendar
"não implemente ainda".

---

## 3. Estrutura do artigo

Orçamento total: ~7.000 palavras (sem referências). Cada seção lista o que
entra, de onde vem (IDs do inventário) e o que **não** entra.

### 3.1. Resumo / Abstract (250 palavras)
Contexto (AnCo, fluxo anterior em Forms + Sheets), objetivo, método (relato
retrospectivo baseado em artefatos), resultados principais (4 reversões, 3
padrões de governança), contribuição transferível. Palavras-chave: Análise
Cognitiva; desenvolvimento assistido por IA; agentes de código; relato de
experiência; revisão de escopo.

### 3.2. Introdução (700 palavras)
- Problema: grupo de pesquisa em AnCo catalogava e analisava literatura em
  planilhas; precisava de plataforma com acervo citável e fluxo de análise.
- Contexto de ferramenta: agentes de código (Claude Code) permitem construir
  rápido; a literatura discute risco de "construir sem entender".
- Pergunta do relato: como governar um agente que constrói mais rápido do que
  o grupo consegue decidir o que quer?
- Contribuição: (1) um contrato de processo reutilizável; (2) a descrição de
  um ciclo parecer → decisão travada → fase → relatório; (3) evidência de que
  reversões são aprendizado de domínio, com custo medido.
- Fora: história do grupo, detalhes da stack.

### 3.3. Referencial breve (600 palavras)
Três fios, cada um com 3–5 referências (a levantar; ver §6):
1. **Análise Cognitiva** (Fróes Burnham): multirreferencialidade, áreas de
   significação, espiral do conhecimento. Usado para justificar D91–D95.
2. **Revisões de escopo e PRISMA-ScR**: o que a plataforma tentou implementar
   (D52–D56) e por que a separação ANCO × PRISMA (D78) é conceitual, não só
   técnica.
3. **Desenvolvimento de software assistido por IA / agentes de código**:
   estudos sobre produtividade, "vibe coding", governança de agentes,
   *human-in-the-loop*. Situar o CLAUDE.md como artefato de governança.
- Opcional: *design-based research* como lente para os ciclos de
  construção → uso → redesenho. Só entra se o veículo for de Educação.

### 3.4. Método do relato (600 palavras)
- Natureza: relato retrospectivo, reconstruído a partir de artefatos
  (§1.1 do inventário): 332 commits, 25 relatórios de fase, 5 planos, 4
  pareceres, 1 auditoria, especificação versionada, memória do agente, banco
  de produção.
- Unidade de análise: a **decisão** (com data, alternativa descartada,
  justificativa, instância decisora, evidência). 109 decisões catalogadas.
- Instâncias decisoras: U, C, E, IA e U←IA. Explicar a convenção.
- **Limites, declarados de frente:** sem transcrições de sessão, sem medição
  de esforço, churn contamina dados com código, e o mesmo agente que
  construiu produziu o inventário. Contramedida: colunas mecânicas (Git,
  banco) separadas de colunas de juízo (humanas), no mesmo espírito de D77.
- Aspectos éticos: consentimento dos nomeados; dados de produção só
  agregados; sem dados de analistas individuais.

### 3.5. Contexto e ponto de partida (500 palavras)
- O grupo, o acervo de fundação (653 registros curados), o fluxo anterior.
- Decisões anteriores ao código: não hospedar obras (D21), URLs citáveis
  (D22), o acervo curado como intocável (D57).
- **O contrato de processo** (Era 0): D01–D12 resumidos em uma tabela
  compacta com 6 linhas (dois documentos com precedência; fases com parada;
  relatório com seção de desvios; quando perguntar; co-autoria declarada;
  memória persistente). Reproduzir o trecho do CLAUDE.md §7 (modelo de
  relatório) como Quadro 1.

### 3.6. O relato: modelagem em quatro eras (2.200 palavras)
Narrativa cronológica, uma subseção por era, cada uma fechando com "o que a
era ensinou sobre o domínio". Usar as datas e a tabela de commits/dia como
Figura 1 (linha do tempo com os hiatos visíveis).

**Era 1 — Fundação (29/04–01/05).** Oito fases em três dias; deploy no mesmo
dia. Decisões de stack tomadas pela IA e documentadas (D14–D20); restrição
física ditando arquitetura (D35: 1,2 GB de RAM). Ensinou: a spec v1 já
continha o rigor que o uso derrubaria; redesign editorial imediato (D38–D40)
mostrou que o público queria a planilha como saída, não como inimigo.

**Era 2 — Confronto com o uso real (03/06–08/06).** As três primeiras
reversões, com o parecer que as precedeu:
- 03/06 peer review → curadoria (D41–D45): quem decidiu foi C.
- 04/06 triagem: parecer com opções A/B/C, IA recomenda A, usuário escolhe B
  (D46); dedup em camadas com a semântica "geradora de candidatos, nunca
  juíza" (D50–D51); DOI comprovadamente não confiável (D58–D59).
- 05/06 PRISMA rigoroso → Revisão ANCO (D61–D67): o parecer diz "NÃO
  implemente ainda"; decisões travadas; só então código; implementado como
  modo aditivo.
- 08/06 sem triagem (D68–D73): três dias depois; sorteio com semente gravada.
- 07/06 auditoria da IA sobre o próprio trabalho (D74–D77).

**Era 3 — Separação estrutural (14/06–17/06).** "Nasceram juntos só porque o
significado de cada um não estava claro" (D78). Refatoração faseada com
gates (D80), única migração destrutiva com backup (D82), relevância delegada
ao ASReview (D84–D87). Ensinou: ANCO e PRISMA têm objetivos antagônicos.

**Era 4 — Fidelidade conceitual (02/07–08/07).** Parecer cotejando a
plataforma com os capítulos de Fróes (D91–D95); tutorial das professoras
como fonte normativa e a tensão registrada entre ele e Fróes (D96–D98);
Matriz proposta e **não** implementada, aguardando coordenação (D95).

### 3.7. O relato: teste de uso (900 palavras)
- Quem usou: 34 usuários (24 analistas, 4 curadores, 6 leitores), 1 projeto
  ANCO com 26 membros, 3 projetos PRISMA.
- Como o uso foi instrumentado: investigação de usabilidade ponta a ponta
  encomendada à IA (10 prioridades) e relatório do que foi aplicado.
- O que o uso exigiu (D99–D109): worklist "à prova de troca de filtro"
  (D100), sorteio = acompanhamento (D101), UI prometendo acesso que o servidor
  negava (D102), editor em página única com abas (D103, escolha do estrutural
  sobre o remendo), perda de trabalho por auto-save (D104), tipo de acesso
  (D109).
- Resultado até 03/09: 51 análises submetidas + 26 rascunhos a partir de 120
  atribuições; 998 itens de corpus; 553 decisões de triagem no PRISMA.
  Leitura honesta: saiu do protótipo, mas o volume novo é fração do legado.
- Tabela 2: métricas de uso. Não interpretar como sucesso; interpretar como
  "validação em curso".

### 3.8. Discussão (1.200 palavras)
Organizar pelos padrões P1–P8 agrupados em quatro achados:
1. **O contrato antes do código funciona como governança** (P1, P2, P3):
   ciclo parecer → decisão travada → fase → relatório; a IA autorizada a
   dizer "não implemente ainda"; aditivo por padrão. Mostrar o custo: 3.808
   linhas removidas em um dia.
2. **Reversões são aprendizado de domínio, não erro** (P4, P5): as quatro
   reversões; restrições físicas e humanas moldando arquitetura mais que
   preferência técnica. A tese em uma linha.
3. **Autoridade humana codificada como restrição** (P8): acervo intocável
   virando 403, isenção, propostas em vez de aplicação, DOI esvaziado com
   aval. O caso do DOI como limite do automatismo.
4. **Trabalho episódico e memória externa** (P6, §8.2 do inventário): 16
   dias em 71, três gerações de modelo, mesmo contrato. Documentação como
   infraestrutura de continuidade.
- **Limites da IA auditando a si mesma** (P7): entra aqui como contraponto
  crítico e prepara a declaração de uso de IA no artigo.
- Transferibilidade: o que outro grupo pode copiar (o contrato, o modelo de
  relatório, a fronteira de decisão) e o que é específico (AnCo, Fróes).

### 3.9. Considerações finais (400 palavras)
- Resposta à pergunta da Introdução.
- O que falta medir (§10 do inventário): transcrições, tempo por fase, taxa
  de aceitação das propostas da IA, defeitos por origem, percepção dos
  analistas, verificação humana do código. Apresentar como agenda, não como
  desculpa.
- Decisão em aberto: 1 revisor com active learning vs. 2 independentes (D90).

### 3.10. Declaração de uso de IA (150 palavras)
O que a IA fez (código, pareceres, auditoria, inventário, apoio à redação),
o que humanos fizeram (decisões de produto, curadoria, revisão do texto),
e a contramedida metodológica adotada.

---

## 4. Figuras e quadros

| # | Conteúdo | Fonte | Produzir com |
|---|---|---|---|
| Figura 1 | Linha do tempo: commits/dia nos 16 dias efetivos, hiatos, eventos-gatilho (reunião, tutorial, relato de analista) | §2 do inventário | gráfico de barras com anotações; dados já no inventário |
| Figura 2 | O ciclo parecer → decisão travada → fase → relatório, com as instâncias U/C/E/IA | P1, P2 | diagrama simples |
| Figura 3 | Arquitetura antes × depois da separação (um app com modos → `apps/anco` + `apps/triagem` com acervo compartilhado) | D78–D83 | diagrama de blocos |
| Figura 4 | As quatro reversões: o que existia, o que substituiu, quem decidiu, data | P4 | tabela visual ou diagrama em cascata |
| Quadro 1 | Modelo de Relatório de Fim de Fase (CLAUDE.md §7) | CLAUDE.md | citação literal |
| Quadro 2 | Regra "quando perguntar / quando não" (CLAUDE.md §8) | CLAUDE.md | citação literal |
| Tabela 1 | Contrato de processo: 6 cláusulas, alternativa descartada, efeito observado | D01–D12 | condensar |
| Tabela 2 | Uso em produção em 03/09/2026 | §8.3 do inventário | direto |
| Tabela 3 | Produção de código por era e modelos de IA | §8.1, §8.2 | direto |
| Apêndice A | Inventário completo D01–D109 (material suplementar, se o veículo permitir) | inventário | exportar |

---

## 5. Roteiro de trabalho

| Etapa | Entrega | Depende de |
|---|---|---|
| 0. Editorial | fechar veículo, autoria, consentimentos, norma de citação | usuário e coordenação |
| 1. Coleta complementar | (a) extrair citações literais dos 4 pareceres e do CLAUDE.md; (b) recontar métricas do banco na data de submissão; (c) **opcional**: questionário curto aos 24 analistas (percepção de uso) — só se houver tempo e aval | — |
| 2. Referencial | levantar 10–15 referências nos três fios (§3.3); verificar cada uma | etapa 0 (norma) |
| 3. Esqueleto | arquivo `docs/artigo/relato-experiencia.md` com todos os títulos e, sob cada um, os IDs e bullets desta seção 3 | — |
| 4. Redação | seções na ordem 3.6 → 3.7 → 3.5 → 3.8 → 3.4 → 3.2 → 3.9 → 3.1 (o relato primeiro, pois é o que existe; Introdução e Resumo por último) | etapa 3 |
| 5. Figuras | Figuras 1–4 e tabelas; conferir números contra o inventário | etapa 1b |
| 6. Revisão de conteúdo | coordenação e curadoria leem as passagens em que são citadas | etapa 4 |
| 7. Revisão de forma | limite de palavras, norma, declaração de IA, anonimização | etapas 0 e 6 |

Divisão de trabalho sugerida: a IA faz etapas 1a, 3, 5 e o primeiro rascunho
da 4; o usuário decide a etapa 0, valida a 2 (nenhuma referência entra sem
verificação humana), reescreve a Discussão e conduz 6 e 7.

---

## 6. Riscos do texto e como evitá-los

- **Catálogo em vez de argumento.** 109 decisões não cabem no corpo. Regra:
  o corpo cita no máximo ~35 IDs; o resto vai ao apêndice.
- **Triunfalismo.** O volume novo (51 análises) é fração do legado (651).
  Dizer isso na seção de uso, não esconder na Discussão.
- **A IA julgando a IA.** Toda afirmação avaliativa sobre qualidade do
  código ou da colaboração precisa de evidência humana ou mecânica; a
  auditoria 8/10 (D74) é autoavaliação e deve ser apresentada como tal.
- **Pessoas reais.** Não atribuir frases a professoras sem consentimento;
  "alunos que querem nota" (D61) é citação sensível; usar só com aval ou
  parafrasear.
- **Referências inventadas.** Nenhuma referência entra sem ter sido aberta
  e conferida por humano.
- **Confundir modelagem com stack.** O artigo é sobre modelar o domínio
  (fluxo, papéis, rigor, conceitos de Fróes), não sobre Django e Docker.
  Stack aparece em uma frase e na Tabela 3.
