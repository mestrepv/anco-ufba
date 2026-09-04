# Construir para descobrir o domínio: relato de experiência do desenvolvimento da Plataforma AnCo com um agente de inteligência artificial

> **Versão 0.1 — primeiro rascunho para leitura e refino do autor.**
> Produzido em 03/09/2026 a partir do plano em `docs/artigo/plano-de-escrita.md`
> e do inventário de decisões em `docs/artigo/inventario-de-decisoes.md`.
>
> **Convenções deste rascunho.**
> - As pessoas envolvidas aparecem **por papel** ("coordenação acadêmica",
>   "curadoria bibliográfica") até que haja consentimento para nomeá-las. A
>   pesquisadora cuja teoria fundamenta o campo é citada pelo nome, como autora
>   publicada.
> - Referências marcadas com **[verificar]** ainda não foram conferidas por
>   humano; referências marcadas com **[a levantar]** são lacunas a preencher.
>   Nenhuma delas deve permanecer no texto submetido sem conferência.
> - Os códigos `D01`…`D109` remetem ao inventário de decisões e devem ser
>   removidos ou convertidos em apêndice na versão final.
> - Trechos entre `⟦ ⟧` são notas do rascunho ao autor, não texto do artigo.

---

## Resumo

Este relato de experiência descreve a modelagem e o teste de uso da Plataforma AnCo, um ambiente colaborativo para catalogar e analisar a literatura sobre Análise Cognitiva, desenvolvido entre abril e julho de 2026 em parceria com um agente de código baseado em inteligência artificial. O grupo de pesquisa que o encomendou trabalhava com formulários e planilhas e precisava de um acervo público citável e de um fluxo de análise governado por curadoria. Em três dias, o agente implantou em produção uma plataforma completa, incluindo revisão por pares, protocolo PRISMA-ScR, medida de concordância entre revisores e calibração. O uso real por 24 analistas, nas semanas seguintes, produziu quatro reversões sucessivas dessas escolhas, todas por decisão acadêmica e não por defeito de implementação. O relato reconstrói essas reversões a partir dos artefatos que o próprio processo deixou: 332 commits, 25 relatórios de fase, quatro pareceres, uma auditoria e a especificação versionada. Argumenta-se que a velocidade do agente permitiu construir antes de compreender o domínio, e que o custo disso foi pago em refatoração, mas com o domínio já compreendido. Isso só foi governável por dois mecanismos: um contrato de processo escrito antes do código, que impôs fases, paradas obrigatórias e relatórios com seção de desvios, e a manutenção explícita da fronteira entre decisão de implementação, decisão de coordenação acadêmica e decisão de curadoria. O texto discute a transferibilidade desses mecanismos e declara os limites de um relato em que o mesmo agente que construiu a plataforma auxiliou a reconstruir a sua história.

**Palavras-chave:** Análise Cognitiva; desenvolvimento de software assistido por inteligência artificial; agentes de código; relato de experiência; revisão de escopo.

⟦Abstract em inglês a produzir depois que o resumo em português estabilizar.⟧

---

## 1. Introdução

Um grupo de pesquisa que estuda Análise Cognitiva (AnCo) acumulou, ao longo de anos, um acervo de mais de mil registros bibliográficos analisados segundo uma matriz própria. O fluxo de trabalho era o de muitos grupos brasileiros: formulários para coletar as análises, planilhas para consolidá-las, e nenhum lugar público onde uma análise pudesse ser lida e citada. O acervo tinha valor, mas não tinha endereço.

Em abril de 2026 o grupo decidiu construir uma plataforma para substituir esse fluxo. O desenvolvedor, autor deste relato, optou por fazê-lo em parceria com um agente de código, isto é, um modelo de linguagem operando com acesso ao repositório, ao terminal e ao ambiente de implantação, capaz de escrever, testar e publicar código de forma autônoma dentro de limites definidos. A escolha respondia a uma restrição prática, a de um único desenvolvedor com tempo intermitente, e a uma curiosidade metodológica: o que acontece quando a capacidade de construir passa a ser maior do que a capacidade do grupo de decidir o que quer construir?

A literatura recente sobre agentes de código concentra-se em produtividade e correção ⟦[a levantar: 2 a 3 estudos empíricos sobre produtividade com assistentes/agentes de código]⟧, e uma crítica corrente, popularizada sob o rótulo de *vibe coding*, aponta o risco de produzir software que funciona sem que ninguém compreenda por quê ⟦[a levantar: origem e crítica do termo]⟧. Este relato olha para um risco vizinho e menos discutido: o de produzir software que funciona e é compreendido, mas que modela um domínio ainda não compreendido pelos próprios pesquisadores. A velocidade do agente torna esse risco concreto porque elimina o intervalo de tempo em que, no desenvolvimento convencional, o domínio costuma amadurecer enquanto o código não existe.

A pergunta que organiza o relato é, portanto: **como governar um agente que constrói mais rápido do que o grupo consegue decidir?** A resposta que a experiência oferece tem três partes, que são também as três contribuições do texto:

1. **Um contrato de processo escrito antes do código**, separado da especificação do produto, que impôs trabalho faseado, parada obrigatória para aprovação humana entre fases e um relatório de fim de fase com uma seção específica de desvios da especificação. Esse contrato, e não a especificação, foi o instrumento que tornou o desenvolvimento auditável.
2. **Um ciclo de decisão em quatro tempos**, parecer, decisão travada, fase e relatório, no qual o agente foi autorizado a recomendar "não implemente ainda" e a distinguir o que era decisão de implementação do que era decisão de coordenação acadêmica ou de curadoria.
3. **Evidência de que as reversões de modelagem foram aprendizado de domínio, não erro de implementação**, com o custo medido em código removido e o ganho descrito em compreensão conceitual do campo.

O texto está organizado assim. A seção 2 situa brevemente os três referenciais em jogo: a Análise Cognitiva como campo, as revisões de escopo e o desenvolvimento assistido por agentes. A seção 3 descreve o método do relato e os seus limites. A seção 4 apresenta o ponto de partida e o contrato de processo. A seção 5 narra a modelagem em quatro eras. A seção 6 descreve o teste de uso. A seção 7 discute os padrões que emergem e a seção 8 conclui com o que falta medir.

---

## 2. Referencial breve

### 2.1. Análise Cognitiva como campo multirreferencial

Fróes Burnham propõe a Análise Cognitiva não como um método pontual, mas como um campo do conhecimento emergente, complexo e multirreferencial, que vem se constituindo de forma dispersa há cerca de setenta anos e que atravessa muitas disciplinas sem se reduzir a nenhuma ⟦Fróes Burnham, capítulos "Aproximações iniciais para sua construção" e "Reconhecendo o antes irreconhecido" [verificar dados bibliográficos]⟧. Ela toma como marco fundador o trabalho de Naess, Christophersen e Kvalø (1956) sobre democracia, ideologia e objetividade ⟦[verificar]⟧, do qual herda dois princípios que se mostraram decisivos para a plataforma: o sistema de referência analítico é construído pelo analista e não encontrado no material, e o trabalho procede por aproximações sucessivas e de forma coletiva.

Dessa proposta, quatro elementos são mobilizados neste relato. Primeiro, a noção de **áreas de significação**, que são os territórios de sentido nos quais a expressão *cognitive analysis* circula, e que Fróes distingue explicitamente das áreas disciplinares ou administrativas. Segundo, a **espiral do trabalho com o conhecimento**, que vai da produção à organização, à acervação e à difusão, e na qual um acervo público citável ocupa duas fases. Terceiro, o papel constitutivo das **comunidades epistêmicas** e da legitimação coletiva, em que Fróes inclui a revisão cega por pares. Quarto, o **diagnóstico de lacunas** que ela própria faz da literatura: ausência de explicitação dos fundamentos teórico-epistemológicos e escassez de estudos sobre as dimensões ética, estética, afetiva e ontológica do conhecer.

A matriz de análise usada pelo grupo, que a plataforma implementa, responde diretamente à primeira lacuna: ela obriga o analista a explicitar epistemologia, teoria, definição do conceito, objeto, objetivo e foco de cada obra analisada.

### 2.2. Revisões de escopo e o PRISMA-ScR

As revisões de escopo (*scoping reviews*) mapeiam a extensão e a natureza da evidência disponível sobre um tema, sem a pretensão de sintetizar resultados como uma revisão sistemática tradicional. O PRISMA-ScR (Tricco et al., 2018 ⟦[verificar]⟧) é a extensão da declaração PRISMA para esse tipo de revisão, com um checklist de 22 itens e a exigência de protocolo *a priori*, triagem por revisores independentes e fluxograma de inclusão e exclusão. A concordância entre revisores é usualmente medida por coeficientes kappa; quando os revisores variam entre registros, o kappa de Fleiss (1971 ⟦[verificar]⟧) é o apropriado, e a escala de Landis e Koch (1977 ⟦[verificar]⟧) fornece os limiares interpretativos correntes.

Esses instrumentos foram integralmente implementados na plataforma e, como se verá, integralmente desligados para o fluxo principal do grupo. A tensão entre eles e a proposta de Fróes não é acidental: uma revisão de escopo busca um rigor reconhecível internacionalmente e opera por critérios de inclusão fixados antes da leitura; a Análise Cognitiva, tal como Fróes a propõe, é permissiva, multirreferencial e desconfia de qualquer recorte que exclua de antemão o que ainda não foi reconhecido.

### 2.3. Desenvolvimento assistido por agentes de código

⟦Seção a completar com 3 a 5 referências verificadas. Fios sugeridos: (a) estudos empíricos de produtividade e qualidade com assistentes de código; (b) discussão de *human-in-the-loop* e níveis de autonomia de agentes; (c) governança de agentes por instruções persistentes, como arquivos de instrução de repositório; (d) críticas ao *vibe coding*. Evitar citar apenas literatura cinzenta.⟧

O que este relato acrescenta a essa discussão não é uma medida de produtividade, que não foi coletada, mas a descrição de um **arranjo de governança** entre humanos e agente, e do que esse arranjo tornou possível observar.

---

## 3. Método do relato

### 3.1. Natureza e fontes

Este é um relato retrospectivo. Ele não se apoia em observação registrada durante o processo, mas na **reconstrução a partir dos artefatos que o próprio processo deixou**. Essa reconstrução foi possível porque o contrato de processo, descrito na seção 4, exigiu que o agente produzisse documentação com estrutura fixa a cada fase. As fontes, com os volumes correspondentes, foram:

| Fonte | Volume | O que oferece |
|---|---|---|
| Histórico Git do ramo principal | 332 commits, 29/04 a 08/07/2026 | cronologia, granularidade, reversões, coautoria declarada do agente |
| Relatórios de fim de fase | 25 relatórios | seções fixas de decisões tomadas, desvios da especificação e dívida técnica |
| Planos de fase | 5 planos | decisões travadas antes da implementação |
| Pareceres e investigações solicitados ao agente | 4 documentos | análises com opções e recomendação, produzidas antes de decidir |
| Auditoria técnica | 1 documento | autoavaliação crítica do agente sobre a plataforma |
| Especificação técnica | v1 a v2.2 e 3 adendos | mudanças de escopo formalizadas |
| Contrato de processo | 1 documento, 12 seções | as regras do trabalho com o agente |
| Memória persistente do agente | 13 arquivos | decisões do usuário com a justificativa registrada |
| Banco de dados de produção | consultas somente de leitura em 03/09/2026 | uso real |

### 3.2. Unidade de análise

A unidade de análise é a **decisão**. Cada decisão foi catalogada com data, alternativa descartada, justificativa, instância decisora e localização da evidência. O inventário resultante tem 109 decisões, das quais este texto cita cerca de um terço; o inventário completo é oferecido como material suplementar.

As instâncias decisoras foram quatro, e o projeto as manteve separadas de forma explícita:

- **U**, o usuário e desenvolvedor, autor deste relato;
- **C**, a coordenação acadêmica do grupo, composta por três professoras;
- **E**, a curadoria bibliográfica, exercida por uma bibliotecária e doutora em Difusão do Conhecimento;
- **IA**, o agente, quando decidiu sozinho um detalhe de implementação e o registrou em relatório.

A notação **U←IA** indica que o agente propôs e o usuário decidiu. A distinção entre essas instâncias não é um artifício do relato: ela estava escrita no contrato de processo e aparece nos próprios pareceres, que separam "decisões da coordenação" de "decisões do implementador".

### 3.3. Limites, declarados de frente

Quatro limites condicionam o que este relato pode afirmar.

**As transcrições das sessões de trabalho não foram preservadas.** O ambiente do agente guarda apenas a sessão corrente. Não há, portanto, registro de prompts, de tentativas descartadas dentro de uma sessão, nem de tempo de interação. Tudo o que se reconstrói aqui é o resultado versionado e o que foi deliberadamente escrito em documento. Isso significa que o relato vê as decisões que sobreviveram, não as que foram abandonadas antes de virar código.

**Não há medição de esforço.** As estimativas em dias que constam do roteiro de fases são previsões, nunca confrontadas com o realizado. As contagens de commits por dia indicam quando houve trabalho versionado, mas um dia sem commit não é necessariamente um dia sem trabalho: a investigação de usabilidade, por exemplo, é datada de 10/06, dentro de um intervalo sem commits.

**As métricas de código misturam código e dados.** O histórico inclui a importação do acervo legado em formato JSON, que sozinho responde por cerca de 121 mil linhas. Onde a distinção importa, o relato separa as linhas de código de aplicação e de templates.

**O mesmo agente que construiu a plataforma produziu o inventário de decisões e auxiliou na redação deste texto.** Esse é o limite mais sério, e a contramedida adotada foi a mesma que o projeto usou ao avaliar a busca semântica: separar as **colunas mecânicas**, isto é, contagens extraídas do Git e do banco, que qualquer pessoa pode reproduzir, das **colunas de juízo**, isto é, as afirmações sobre o que uma decisão significou, que são de responsabilidade dos autores humanos e foram revisadas por eles. Onde o texto reproduz uma avaliação feita pelo agente sobre o próprio trabalho, ele a apresenta como autoavaliação.

### 3.4. Aspectos éticos

As pessoas que tomaram decisões relatadas aqui são identificadas por papel. Os dados de uso são apresentados de forma agregada. Nenhuma análise individual, nem o desempenho de nenhum analista, é descrito. ⟦Confirmar com o veículo se um relato de experiência sem coleta de dados de participantes dispensa parecer de comitê de ética; se o questionário aos analistas sugerido na seção 8 for aplicado, isso muda.⟧

---

## 4. Ponto de partida e o contrato de processo

### 4.1. O que existia antes do código

Três decisões foram tomadas antes de qualquer linha de código e nunca foram revertidas.

A primeira é jurídica e editorial: **a plataforma não hospeda obras de terceiros**. Ela guarda metadados e links; o conteúdo autoral que hospeda é a análise e a resenha produzidas pelo grupo, sob licença Creative Commons (D21).

A segunda é de infraestrutura acadêmica: **as URLs são estáveis e citáveis desde o primeiro dia** (D22). Cada artigo e cada análise têm um endereço permanente, porque, como registra a especificação, mudar a URL depois quebra citações.

A terceira é o contrato de dados mais importante do projeto: **o acervo curado é intocável** (D57). O acervo de fundação, com 653 registros, passou por curadoria bibliográfica antes de entrar na plataforma. A regra decorrente é que toda mudança em dado curado é uma proposta, apresentada em arquivo paralelo, e nunca uma aplicação automática. Essa regra atravessa todas as eras do relato e será retomada na seção 7.

### 4.2. O contrato de processo

Antes de escrever a especificação do produto, o desenvolvedor escreveu um documento que governa o processo do agente. A separação entre os dois foi, em si, a primeira decisão (D01): a especificação prevalece para decisões de produto; o contrato prevalece para decisões de processo. A justificativa registrada é evitar que o agente "reescreva o produto" ao ajustar o processo.

O Quadro 1 condensa as cláusulas do contrato que se mostraram determinantes.

**Quadro 1 — Cláusulas do contrato de processo e seu efeito observado**

| Cláusula | Alternativa descartada | Efeito observado ao longo do projeto |
|---|---|---|
| Trabalho **faseado**, uma fase por vez, com **parada obrigatória** para aprovação humana; proibido implementar código de fase futura (D02) | desenvolvimento contínuo dirigido pelo agente | manteve o humano no controle de escopo; tornou o trabalho auditável em blocos; foi reaplicado, sem alteração, a uma refatoração estrutural em junho |
| **Relatório de fim de fase** com seções fixas, entre elas *desvios da especificação* e *dívida técnica deixada* (D03) | registro livre de mudanças | forçou o agente a declarar onde divergiu e o que adiou; é o que tornou este relato possível |
| Regra de **quando perguntar e quando não** (D04): decisão de produto ou trade-off visível ao usuário, perguntar com duas ou três opções; detalhe técnico interno, decidir e documentar | perguntar sempre, ou nunca | calibrou a autonomia; as decisões marcadas **IA** no inventário são exatamente as da segunda classe |
| Tom contratado: "se discordar da especificação, diga e proponha alternativa; você é o implementador, não um executor passivo" (D05) | agente puramente executor | autorizou os pareceres em que o agente recomendou não implementar |
| **Coautoria declarada** em todo commit (D08) | autoria silenciosa | 344 marcadores de coautoria em 332 commits; a participação do agente é rastreável commit a commit |
| Testes obrigatórios em validações, serviços de domínio e fluxos críticos; cobertura mínima de 70% do código novo; integração contínua desde a primeira fase (D09) | testar ao final | trava de qualidade que o agente não podia negociar; a auditoria de junho encontrou a integração contínua rodando sem uma extensão de banco necessária, e isso foi corrigido no mesmo dia |
| Lista de proibições: sem dependência sem justificativa no commit, sem abstração especulativa, sem reescrever a especificação por conta própria (D10) | confiar no julgamento do agente | conteve os vícios típicos de geração automática; a duplicação intencional de código entre módulos foi uma decisão registrada, não um acidente |
| **Memória persistente** do agente em arquivos, cada um com a justificativa e o modo de aplicar (D11) | reconstruir o contexto a cada sessão | permitiu retomar o trabalho após intervalos de até cinco semanas |

O Quadro 2 reproduz o modelo de relatório de fim de fase tal como consta do contrato, porque a sua estrutura é o que distingue esse arranjo de um registro de mudanças convencional.

**Quadro 2 — Modelo do Relatório de Fim de Fase (reproduzido do contrato de processo)**

```
# Relatório — Fase N: <Nome da fase>

## O que foi entregue
## Critério de aceite (da especificação)
## Decisões tomadas
   Decisões de implementação que não estavam no documento de
   especificação e que valem registrar.
## Desvios da especificação
   Casos onde implementei algo diferente do documento. Cada item com:
   o que a especificação dizia; o que foi feito; por quê.
## Dívida técnica deixada
   Itens que decidi adiar conscientemente.
## Métricas
## Pendências para o usuário
```

Duas observações sobre o contrato. A primeira é que ele foi **mutável em tempo de execução**: em ao menos uma fase o usuário o sobrepôs, pedindo que o agente executasse a fase inteira sem interrupção e fizesse um único commit ao final, contra a convenção de commits atômicos que o próprio contrato estabelecia (D07). A segunda é que o contrato **não mudou quando a ferramenta mudou**: o projeto atravessou três gerações do modelo subjacente entre abril e julho, com o mesmo documento de processo. Voltaremos a isso na discussão.

---

## 5. O relato: modelagem em quatro eras

O desenvolvimento durou 71 dias corridos, mas ocorreu em apenas **16 dias com trabalho versionado**, agrupados em quatro blocos densos separados por intervalos longos. A Figura 1 mostra essa distribuição.

**Figura 1 — Commits por dia nos 16 dias efetivos, com os intervalos sem commit**

```
2026-04-29  ████████████████████████████████████████████████████████ 58
2026-04-30  ████████████ 12
2026-05-01  ████ 4
            ‥‥‥‥‥‥‥‥‥‥ 33 dias sem commit ‥‥‥‥‥‥‥‥‥‥
2026-06-03  ████████████████████████████████ 32
2026-06-04  █████████████████████████████████████████ 41
2026-06-05  ███████████████ 15
2026-06-06  ████████████████████████████ 28
2026-06-07  ███████ 7
2026-06-08  ██████████████████████████████████████████ 42
            ‥‥‥‥‥‥‥‥‥‥ 6 dias sem commit ‥‥‥‥‥‥‥‥‥‥
2026-06-14  ████████████████████████ 24
2026-06-17  ██████ 6
            ‥‥‥‥‥‥‥‥‥‥ 15 dias sem commit ‥‥‥‥‥‥‥‥‥‥
2026-07-02  ███ 3
2026-07-05  █████████ 9
2026-07-06  ████████████████ 16
2026-07-07  ██████████████████ 18
2026-07-08  █████████████████ 17
```

⟦Converter em gráfico de barras com anotações dos eventos-gatilho: reunião da coordenação (03/06), parecer de triagem (04/06), decisão da coordenação (05/06), decisão da professora (08/06), decisão da separação (14/06), parecer sobre Fróes e tutorial das professoras (02 a 08/07).⟧

Cada bloco foi disparado por um evento externo ao código: uma reunião, um documento recebido, um problema relatado por quem usava a plataforma. O desenvolvimento não foi contínuo; foi **episódico e reativo ao uso**. As quatro eras a seguir correspondem aos quatro blocos.

### 5.1. Era 1 — Fundação: oito fases em três dias (29/04 a 01/05)

No primeiro dia, o agente produziu 58 commits e cerca de 11 mil linhas de código de aplicação e templates, cobrindo as fases 0 a 8 do roteiro: fundação, modelagem, autenticação, criação e edição de análises, revisão por pares, acervo público, saúde de links, produção e busca semântica. **O deploy em produção aconteceu no mesmo dia em que o projeto nasceu.**

Essa velocidade merece ser lida com cuidado. A especificação estava escrita e detalhada, com modelos de dados esboçados e critérios de aceite por fase; o agente não inventou o produto, implementou-o. Ainda assim, oito fases planejadas para cerca de vinte dias de trabalho humano foram entregues em um, e cada uma teve seu relatório com decisões e desvios declarados.

As decisões dessa era são de dois tipos. As **decisões de implementação tomadas pelo agente** e registradas em relatório (D14 a D20, D24 a D32) são as que o contrato lhe autorizava a tomar: escolha de bibliotecas com justificativa, heurísticas de normalização para dados corrompidos do legado, notificações que falham silenciosamente para que um erro de e-mail não derrube uma publicação. Uma delas ilustra bem o padrão: o roteiro previa um ambiente de containers completo desde a primeira fase, e o agente propôs adiar dois serviços que ainda não tinham consumidor, com a justificativa de que um serviço sem dependência entraria em ciclo de erro; o usuário aprovou (D17).

O segundo tipo são as **decisões ditadas por restrições físicas**. A mais nítida é a do modelo de embeddings para a busca semântica (D35): a especificação apontava para um modelo de 1024 dimensões que exige de 3 a 4 GB de memória; o servidor tinha cerca de 1,2 GB livres. O agente escolheu um modelo multilíngue de 384 dimensões e documentou a razão. A arquitetura foi decidida pela memória disponível, não por preferência técnica.

Dois dias depois do deploy, o usuário decidiu um redesign editorial de todas as páginas públicas (D38). A decisão mais reveladora desse redesign é a de oferecer o acervo público também como **planilha filtrável** (D39): o público-alvo já trabalhava em planilha, e a plataforma, em vez de negar esse hábito, passou a oferecer a planilha como saída.

**O que a Era 1 ensinou sobre o domínio.** Pouco, e esse é o ponto. A especificação v1 já continha o rigor metodológico completo, dois revisores estruturais e dois cegos por análise, publicação automática por consenso, e ele foi implementado sem que ninguém do grupo o tivesse experimentado. O que o uso derrubaria nas semanas seguintes estava todo ali, funcionando.

### 5.2. Era 2 — O confronto com o uso real (03/06 a 08/06)

Cinco semanas de silêncio, e o projeto volta com 165 commits em seis dias. É a era das reversões. Quase tudo o que muda aqui desfaz uma decisão da Era 1, e em nenhum caso por defeito de implementação.

**Primeira reversão (03/06): revisão por pares → curadoria.** A coordenação acadêmica decidiu que as análises não passariam mais por revisão por pares. O fluxo passou a ser rascunho, submissão e aprovação por um curador (D41). A justificativa registrada é que o ritual de revisão dupla era fricção excessiva para o perfil real dos participantes. Toda a fase 4, construída no primeiro dia, deixou de ser usada para análises.

Duas decisões acompanharam essa reversão e mostram como o contrato de processo operou. A primeira: o agente propôs, e o usuário aceitou, que **a revisão cega sobrevivesse para a resenha crítica**, que passou a ser uma entidade própria (D42). O investimento da fase 4 foi preservado onde fazia sentido, isto é, no conteúdo autoral. A segunda: o desvio foi registrado como **adendo à especificação, não como reescrita** das seções originais (D43), para manter legível o que era antes e por que mudou.

**A triagem: um parecer antes do código (03 a 04/06).** O grupo tinha um sistema de triagem de literatura em uso, construído em outra tecnologia para um projeto distinto, e queria trazê-lo para a plataforma. Antes de escrever código, o usuário pediu ao agente um **parecer de viabilidade**. O parecer, datado de 03/06 e explícito quanto a não ter alterado nenhuma linha de código, oferecia três opções: integração leve por importação, módulo nativo, ou fusão das aplicações, esta última classificada como não recomendada. Recomendou começar pela integração leve e promover ao módulo nativo apenas "se a triagem for atividade recorrente do grupo, não pontual".

**A decisão do usuário foi ir direto ao módulo nativo** (D46), porque a recorrência era prevista e a divergência de tecnologias era o principal atrito. O parecer não foi seguido na recomendação, mas cumpriu sua função: tornou a escolha explícita, com alternativas e critérios registrados.

Duas decisões dessa etapa são metodologicamente importantes. A **deduplicação em camadas** (D50): chave exata quando disponível, depois título normalizado e ano, e só no resíduo a similaridade semântica por embeddings. O DOI não entrou como chave de identidade, e a razão veio da curadoria: dos 311 DOIs auditados contra a fonte oficial, 68 estavam errados, atribuídos por um processo automático anterior a artigos diferentes (D58). Um dado que seria a chave natural em qualquer outro acervo era, neste, comprovadamente não confiável. A correção só foi aplicada com aval da curadora, com cópia de segurança prévia, e preferiu-se **esvaziar 21 DOIs** sem substituto confiável a manter um identificador que apontava para outra obra (D59).

A segunda decisão é a regra sobre a camada semântica: ela é **geradora de candidatos, nunca juíza de identidade** (D51). Um teste com 80 pares mostrou que duplicatas reais tinham similaridade mediana de 0,86, enquanto pares sobre o mesmo tema mas de obras diferentes tinham 0,27; ainda assim, a faixa intermediária foi reservada à revisão humana, porque, como registra o relatório, o embedding "mede assunto, não obra".

**Rigor construído e desligado (04 a 05/06).** Com o módulo nativo, o agente implementou o instrumental completo de uma revisão de escopo: kappa de Fleiss, escolhido em vez do de Cohen porque os pares de revisores variavam por registro (D52); gate de calibração em 0,60 exibido ao curador, que decide (D53); triagem em duas etapas como opção desligada por padrão (D54); protocolo *a priori* com registro externo e versão travada (D55).

**Segunda reversão (05/06): PRISMA rigoroso → "Revisão ANCO".** No dia seguinte à entrega desse instrumental, a coordenação decidiu adiá-lo. A justificativa registrada é que os participantes daquele momento se comportavam como estudantes cumprindo uma tarefa avaliada, e que revisão dupla cega, kappa e calibração eram fricção excessiva **naquele momento** (D61). Note-se o advérbio: o rigor não foi julgado errado, foi julgado prematuro para aquele grupo.

O parecer que embasou essa reversão é o documento mais importante do relato para a tese da fronteira de decisão. Datado de 05/06, ele avaliou a viabilidade do fluxo simplificado e concluiu que era "viável e de baixo custo", mas abriu o sumário executivo assim:

> "Recomendação: NÃO implementar ainda. Antes, fechar 4 decisões de produto e validar 1 premissa. São decisões da coordenação, não do implementador."

As quatro decisões e a premissa foram levadas à coordenação, decididas e **travadas por escrito no mesmo dia**, em uma seção do parecer intitulada "decisões da coordenação", que o documento declara como "especificação consolidada e autoritativa" com precedência sobre a análise técnica que a fundamenta. Só então veio o código. Entre as decisões travadas: o fluxo simplificado não se chama PRISMA, chama-se Revisão ANCO, e deve "automatizar o mais próximo possível do que já se faz na disciplina"; a relevância é calculada por contagem de termos da estratégia de busca, sem embeddings, com a vantagem registrada de ser "explicável ao analista"; cada analista recebe cota de cinco artigos; a revisão dupla, quando houver, é conciliada pelo curador e não por algoritmo (D63 a D66).

A implementação seguiu o princípio que o mesmo parecer enunciou: "não se trata de desligar o protocolo rigoroso; trata-se de adicionar um modo de operação ao lado dele". O fluxo simplificado entrou como **modo por projeto**, com o rigoroso intacto e oculto (D62). O relatório da fase registra o desvio da especificação em uma linha: "o plano em si é um desvio deliberado e aditivo do fluxo PRISMA-ScR, comutado por modo e reversível por projeto".

**Terceira reversão (08/06): autotriagem → sem triagem.** Três dias depois, a professora responsável pela disciplina decidiu que o modo ANCO não teria triagem alguma: todo registro importado entra direto no corpus, de qualquer tipo de documento (D68, D73). O agente propôs redefinir o modo existente em vez de criar um terceiro (D69), e o usuário decidiu que a migração de dados reincluiria as exclusões feitas pela autotriagem, agora obsoletas, sem jamais tocar o legado (D70). Duas decisões de implementação dessa etapa mostram a preocupação com auditabilidade: a inclusão automática **não cria um revisor fictício**, o campo de decisor fica vazio, para que ela seja auditável como automática (D71); e o sorteio de artigos para análise passou a ser aleatório puro **com semente gravada**, para ser reprodutível (D72).

**O agente auditando o próprio trabalho (07/06).** Entre a segunda e a terceira reversão, o usuário pediu ao agente uma auditoria técnica crítica da plataforma que ele mesmo construíra (D74). O resultado foi um documento que se abre com o veredito de que aquela "não é uma aplicação amadora", atribui nota 8 em 10 e lista dois achados de severidade alta, seis médios e seis baixos. Os dois altos eram reais e foram corrigidos no mesmo dia: a integração contínua rodava sem a extensão de banco que uma migração exigia, e o build não era reprodutível por falta de arquivo de travamento de dependências (D75). A auditoria também classificou como dívida consciente a duplicação de cerca de 650 linhas entre os módulos de triagem e de acervo, com a justificativa de que a generalização prematura era o risco maior (D76). Este relato apresenta esses resultados como o que são: autoavaliação de um agente sobre o próprio produto, útil para encontrar defeitos mecânicos, e não como juízo independente de qualidade.

**O que a Era 2 ensinou sobre o domínio.** Que o grupo não era o grupo imaginado pela especificação. A revisão por pares, o protocolo e a calibração pressupunham revisores independentes com tempo e treino; o grupo real era uma turma de disciplina, com prazos e nota, e uma coordenação que queria ver a análise acontecer antes de medir sua concordância. Nenhuma dessas informações estava disponível em abril, e nenhuma delas poderia ter sido obtida sem um sistema funcionando para ser usado.

### 5.3. Era 3 — A separação estrutural (14/06 a 17/06)

Ao fim da Era 2, os dois fluxos, o rigoroso e o simplificado, viviam sob o mesmo módulo, comutados por um campo de modo e por cerca de 25 ramificações condicionais no código. Em 14/06 o usuário decidiu separá-los em módulos completamente independentes (D78). O plano da separação registra a razão em termos que não são técnicos:

> "ANCO e PRISMA-ScR têm objetivos antagônicos e não podem se misturar."

E o inventário guarda a frase do usuário que resume a era inteira: os dois "nasceram juntos só porque, na época, o significado de cada um não estava claro".

O critério de corte foi conceitual: PRISMA é um pipeline de triagem; ANCO é importação, corpus, sorteio e análise. O acervo permanece compartilhado, porque, como diz o plano, "não é misturar; é a estante publicada" (D79).

Três decisões dessa era mostram o contrato de processo operando sobre uma refatoração, e não sobre funcionalidade nova. A separação foi executada em **cinco fases com aprovação humana entre elas** (D80): inventário, módulo novo atrás de uma chave desligada, corte de tráfego com redirecionamentos permanentes, limpeza destrutiva e controle de acesso por módulo. A fase de módulo novo **duplicou o código** de importação e deduplicação em vez de compartilhá-lo (D81), por decisão explícita do usuário em favor do isolamento real, "quebrar ou mudar um não afeta o outro", e com a dívida aceita por escrito. E a única migração destrutiva de todo o projeto (D82) foi precedida de inventário dos dados de produção, cópia de segurança rotulada e da constatação de que o campo de relevância removido era calculado e gravado, mas **nunca lido** pelo fluxo rigoroso. O custo mensurável dessa era está em um número: 3.808 linhas removidas em um único dia.

A separação também redefiniu de onde viria a relevância no fluxo rigoroso: em vez de reimplementá-la, o projeto decidiu integrar uma ferramenta de código aberto de triagem assistida por aprendizado ativo, como serviço ao lado da plataforma (D84). O piloto revelou que a ferramenta não tinha autenticação própria, e ela foi publicada apenas em interface local, acessível por túnel (D87). Uma decisão metodológica ficou explicitamente em aberto para a coordenação, porque define o desenho do estudo e não a implementação: um revisor assistido por aprendizado ativo, ou dois revisores independentes (D90).

**O que a Era 3 ensinou sobre o domínio.** Que a distinção entre os dois fluxos não era de grau de rigor, mas de finalidade. Uma revisão de escopo tria para excluir e produzir um fluxograma reconhecível; a Análise Cognitiva, no sentido de Fróes, inclui para reconhecer o que ainda não foi reconhecido. Um mesmo módulo com um campo de modo tratava essa diferença como parâmetro. A separação a tratou como o que ela é.

### 5.4. Era 4 — Fidelidade conceitual (02/07 a 08/07)

A última era começa com um pedido diferente dos anteriores. O usuário pediu ao agente um **parecer cotejando a plataforma com os dois capítulos originais** de Fróes Burnham sobre a Análise Cognitiva. O parecer, que declara não ter alterado nenhum dado, faz uma leitura dos capítulos e depois confronta o acervo curado com ela.

O achado central é quantitativo e conceitual ao mesmo tempo. O campo de área dos artigos estava preenchido, em 93% dos casos, com as grandes áreas da classificação administrativa da pós-graduação brasileira. O parecer releu o acervo pelas áreas de significação de Fróes, usando o campo de foco, e mostrou o descasamento em ambas as direções: uma única área de significação se espalhava por até 14 grandes áreas administrativas, e uma única grande área abrigava até 10 significações. A conclusão do parecer:

> "Não tratar a área CAPES como a classificação do campo. [...] Sem essa separação, a plataforma corre o risco de re-disciplinarizar justamente o campo que Fróes quer instituir como multirreferencial."

A decisão decorrente (D91) foi que a classificação administrativa e a área de significação são **dimensões irredutíveis** e devem coexistir sem fusão. O rótulo do editor, que em 03/06 adotara o menu da classificação administrativa, foi revertido para "Área de conhecimento" (D92).

O mesmo parecer auditou os vocabulários de foco e de epistemologia e encontrou três patologias: dispersão, com 89% e 70% de termos que ocorrem uma única vez; ruído de valores-sentinela vazados para o dado; e mistura de níveis, com rótulos de área aparecendo no campo de epistemologia e vice-versa. A resposta foi uma **camada de vocabulário controlado que mapeia sem sobrescrever** (D60) e uma facetação da epistemologia em paradigma, método e disciplina, **aditiva e reversível por comando** (D93). Nada disso tocou o acervo curado.

Duas decisões dessa era mostram o agente sendo corrigido pela teoria. O parecer sobre Fróes organizara sua leitura em torno de uma distinção entre sentido estreito e sentido amplo da expressão *cognitive analysis*. O protocolo de análise do grupo foi depois corrigido para **não** usar essa dicotomia binária (D94), porque Fróes fala em dispersão e polissemia de um campo emergente, e o binário "arriscaria excluir obras que ela incluiria". A ferramenta de leitura que o agente trouxe era mais nítida do que o campo permite.

A segunda: o parecer identificou que a matriz de análise não tinha campos para as dimensões que Fróes diz faltarem na literatura, e propôs cinco eixos adicionais, opcionais e aditivos. **Nada foi implementado** (D95). A proposta ficou registrada como documento para a coordenação, porque a matriz é objeto de decisão acadêmica, não de produto.

Em 08/07, o grupo recebeu das professoras um tutorial de análise, e o editor foi realinhado a ele: ordem das abas, numeração dos itens, posição dos resultados antes dos referenciais (D96). O tutorial passou a ser fonte normativa acima do desenho anterior. O relatório da fase registra, com franqueza incomum, que **dois textos entraram sem confirmação das professoras** e que um deles, o critério de pertinência, "está em tensão com a fidelidade a Fróes" estabelecida dias antes, porque substituía um critério inclusivo por um restritivo; foi marcado como reversão barata (D97). E o usuário decidiu, contra a letra do tutorial que o marcava como opcional, que o contexto de produção da obra seria obrigatório na submissão (D98).

**O que a Era 4 ensinou sobre o domínio.** Que a fidelidade a uma teoria não é uma propriedade que se implementa de uma vez. Ela é um cotejo permanente entre o que o instrumento faz, o que a teoria diz e o que as pessoas que praticam a teoria pedem, e esses três podem estar em tensão no mesmo dia.

---

## 6. O relato: teste de uso

### 6.1. Quem usou

Em 03/09/2026, a plataforma tinha 34 usuários: 24 analistas, 4 curadores e 6 leitores. O módulo ANCO tinha um projeto com 26 membros e 31 fontes de importação; o módulo PRISMA tinha três projetos. A Tabela 1 apresenta o uso acumulado.

**Tabela 1 — Uso em produção em 03/09/2026**

| Indicador | Valor |
|---|---|
| Artigos no acervo | 1.459, dos quais 651 do acervo de fundação |
| Análises | 730: 651 de fundação, 51 submetidas, 26 em rascunho, 1 despublicada, 1 rejeitada |
| Módulo ANCO | 1 projeto, 26 membros, 31 fontes, 998 itens de corpus, 2 sorteios, 120 atribuições de análise |
| Módulo PRISMA | 3 projetos, 5 buscas, 690 registros, 553 decisões de triagem |
| Vocabulário controlado | 753 termos |
| Serviços em produção | aplicação, worker, banco com extensão vetorial, cache, embeddings, triagem assistida |

A leitura honesta desses números é a seguinte. O acervo de fundação continua sendo a maior parte do conteúdo público. O trabalho novo da comunidade está em 51 análises submetidas e 26 em rascunho, produzidas por 24 analistas a partir de 120 artigos sorteados. A plataforma saiu do protótipo e está em uso, mas o volume novo é uma fração do legado. **A validação está em curso, não concluída.**

### 6.2. Como o uso foi observado

O uso não foi observado por instrumento formal. Foi observado de duas maneiras. A primeira, indireta: problemas relatados pelos analistas ao grupo, por canais informais, chegaram ao desenvolvedor e viraram correções. A segunda, deliberada: em 10/06 o usuário encomendou ao agente uma **investigação de usabilidade ponta a ponta**, do cadastro à análise, com o objetivo declarado de tornar o sistema "fácil até para pessoas com muita dificuldade com sistemas web".

A investigação concluiu que o problema "não é o desenho de cada tela isolada; é a jornada como um todo", e identificou três falhas transversais: esperas e atribuições silenciosas, em que a pessoa era aprovada como analista ou recebia artigos sem ser avisada; jargão acadêmico e técnico exposto na interface, como "corpus", "deduplicação", "epistemologia" e valores de similaridade; e carga cognitiva na análise, com cerca de 19 campos obrigatórios de texto livre cujos termos de protocolo não estavam embutidos no editor. Produziu dez prioridades, e o relatório de aplicação registrou o que foi feito e o que ficou de fora, incluindo a adaptação a uma decisão do grupo: não haveria notificação por e-mail, porque o aviso do sorteio seria feito manualmente pelo canal de mensagens do grupo.

### 6.3. O que o uso exigiu

As decisões de julho (D99 a D109) são todas respostas a algo que aconteceu com alguém usando a plataforma. Cinco delas ilustram o tipo de aprendizado que só o uso produz.

**Uma lista de trabalho sem filtros** (D100). O analista tinha uma tela para escolher o que analisar, com filtros por projeto, base e situação. Os analistas se perdiam trocando de filtro e não sabiam o que era deles. A solução foi uma lista dedicada, chamada "Sua análise cognitiva", que mostra apenas os artigos sorteados para aquela pessoa e não tem filtro algum. O relatório a descreve como "à prova de troca de filtro".

**Sorteio e acompanhamento são a mesma pergunta** (D101). Havia uma tela de sorteio e outra, densa, de acompanhamento por analista. Ambas respondiam à pergunta "quem está com o quê e em que estado". Foram unificadas, e a antiga aposentada por redirecionamento.

**A interface prometia o que o servidor negava** (D102). A fila de curadoria aparecia no menu de professoras que tinham papel de curadora no projeto, mas o servidor exigia papel de curadora global e respondia com erro de acesso. Duas professoras foram promovidas. O defeito não estava em nenhum dos dois lados isoladamente; estava no desencontro entre eles, que só o uso revela.

**Perda de trabalho** (D104). O salvamento automático parcial, ao gravar a aba em edição, apagava campos preenchidos nas outras abas. Analistas perderam texto. Foi corrigido, e junto com ele a exibição de prazos e horários, que estava em fuso errado.

**Estrutural em vez de remendo** (D103). O editor de análise tinha quatro abas servidas como páginas separadas, e a troca de aba sem salvar perdia o conteúdo. O agente apresentou duas correções: interceptar o clique e salvar antes de trocar, ou reescrever o editor como página única com abas no cliente. O usuário perguntou se a primeira era "profissional ou gambiarra"; o agente respondeu que era remendo; o usuário escolheu a refatoração. Essa preferência, "sempre a solução profissional, não a gambiarra", ficou registrada na memória do agente como instrução permanente (D12).

Duas outras decisões mostram o contrato de dados operando no uso. Os artigos importados em lote chegavam com resumos truncados e sem palavras-chave; um comando de preenchimento a partir de fontes bibliográficas abertas foi escrito para **aplicar no acervo novo e apenas propor no acervo de fundação** (D105). E quando um curador aprovou uma análise por engano, criou-se a possibilidade de despublicar e devolver ao analista (D108): uma válvula de reversão para erro humano da própria curadoria.

---

## 7. Discussão

Os oito padrões recorrentes identificados no inventário organizam-se em quatro achados. Cada um é apresentado com a evidência que o sustenta e com o seu custo, porque um relato que só mostra ganhos não é um relato.

### 7.1. O contrato antes do código funciona como governança

Nenhuma das grandes mudanças de modelagem começou por código. Em todas, o usuário pediu primeiro um parecer ao agente, com opções e recomendação; a coordenação ou a curadoria decidiu; a decisão foi travada em documento datado; só então veio a fase de implementação, encerrada por relatório. Esse **ciclo em quatro tempos** é o mecanismo central da experiência, e ele só existiu porque o contrato de processo o exigia.

Dois aspectos do ciclo merecem destaque. O primeiro é que o agente foi **autorizado a dizer "não implemente ainda"**, e o fez no momento em que mais importava: quando o fluxo simplificado tinha viabilidade técnica confirmada e o caminho mais rápido seria implementá-lo. O parecer de 05/06 separou o que era decisão de produto do que era decisão de implementação e devolveu as primeiras a quem cabiam. Essa fronteira, entre o que o agente pode decidir e o que deve devolver, é provavelmente o achado mais transferível deste relato, e ela não depende da ferramenta: depende de estar escrita e de ser respeitada por quem opera a ferramenta.

O segundo aspecto é o padrão **aditivo por padrão, destrutivo por exceção documentada**. O fluxo simplificado entrou como modo ao lado do rigoroso; a triagem em duas etapas entrou desligada; o acesso por módulo entrou como chave global e por usuário; a facetação do vocabulário entrou com comando de desfazer; os eixos adicionais da matriz entraram como proposta não implementada. Houve uma única migração destrutiva em 71 dias, precedida de inventário, cópia de segurança e da prova de que o dado removido nunca era lido.

O custo desse padrão é real e mensurável. Cada camada aditiva é código que precisa ser mantido enquanto a decisão que a justificou não é revista, e a separação de junho removeu 3.808 linhas em um dia, boa parte delas camadas aditivas dos dias anteriores. O padrão troca velocidade de decisão por volume de código, e a troca só compensa se a limpeza acontecer. Aqui aconteceu porque o contrato previa fases de limpeza com a mesma disciplina das fases de construção.

### 7.2. Reversões são aprendizado de domínio, não erro

As quatro reversões, de peer review para curadoria, de PRISMA rigoroso para Revisão ANCO, de autotriagem para sem triagem, e de um módulo com modos para dois módulos, têm uma propriedade em comum: **todas foram decididas por instância acadêmica após contato com o uso real**, e nenhuma corrigiu um defeito de implementação. O código revertido funcionava. O que não funcionava era a premissa sobre o grupo e sobre o campo.

Isso permite formular a tese do relato em uma linha: **a velocidade do agente permitiu construir antes de compreender o domínio, e o custo disso foi pago em refatoração, mas pago com o domínio já compreendido.** A separação de junho só pôde ser feita com o critério de corte certo porque a Era 2 tinha mostrado, com um sistema em uso, que os dois fluxos tinham finalidades antagônicas. Em abril, quando "o significado de cada um não estava claro", a separação teria sido feita com o critério errado, ou não teria sido feita.

Vale insistir em que as reversões não foram causadas por preferência técnica, e sim por restrições **físicas e humanas** que a especificação não conhecia. A memória livre do servidor definiu o modelo de embeddings. A inexistência de interfaces programáticas nas bases bibliográficas definiu a ingestão por arquivo. O perfil dos participantes desligou o rigor metodológico. Um erro de metadado histórico proibiu o DOI como chave. Uma interface que prometia o que o servidor negava forçou a promoção de duas curadoras. Em todos esses casos, a arquitetura foi moldada pelo que existia, e o que existia só apareceu com o uso.

Há uma leitura desconfortável desses fatos que o relato não deve evitar. Se o grupo tivesse passado as cinco semanas de maio usando planilhas e conversando sobre o que queria, em vez de ter um sistema completo para experimentar, teria chegado às mesmas conclusões? Talvez, e mais barato. O que a experiência sugere, sem provar, é que algumas dessas conclusões, em particular a de que a triagem não cabia no fluxo da disciplina, só se tornaram visíveis quando pessoas concretas tentaram triar. O sistema funcionou como instrumento de descoberta do domínio, e essa função tem um custo que se paga em código descartado.

### 7.3. Autoridade humana codificada como restrição de sistema

O contrato "o acervo de fundação é intocável", estabelecido pela curadoria bibliográfica antes do código, atravessou todas as eras e converteu-se em código de cinco formas distintas: analistas recebem erro de acesso ao tentar analisar um artigo do legado; registros que coincidem com o acervo são isentos de triagem no fluxo ANCO; os comandos de preenchimento de metadados aplicam no acervo novo e apenas propõem no de fundação; a correção de DOIs só foi aplicada com aval da curadora e cópia de segurança prévia; e os vocabulários foram governados por uma camada de mapeamento que preserva o valor original.

Esse é o exemplo mais nítido, no projeto, de **autoridade humana traduzida em restrição de sistema**. A curadora não precisou revisar cada operação do agente sobre o acervo; bastou que a regra estivesse escrita e que o agente a tivesse internalizado como restrição de projeto, o que a memória persistente garantiu entre sessões.

O caso do DOI é o limite instrutivo. Um processo automático anterior à plataforma atribuíra DOIs errados a mais de um quinto dos registros auditados. A plataforma poderia ter corrigido tudo automaticamente contra a fonte oficial; em vez disso, apresentou a lista, a curadora decidiu, e 21 registros ficaram sem DOI porque não havia substituto confiável. O automatismo teria produzido um acervo mais completo e menos verdadeiro. A regra de que dado curado só muda por decisão humana custou completude e comprou confiabilidade, e essa troca é uma decisão de curadoria, não de engenharia.

### 7.4. Trabalho episódico e memória externa

Dezesseis dias de trabalho versionado em 71, com intervalos de até cinco semanas, é um padrão que o desenvolvimento assistido por agente torna viável e que o desenvolvimento convencional dificilmente permitiria. Em cada retomada, o agente não tinha memória da sessão anterior. O que atravessou os intervalos foi um conjunto de documentos: o contrato de processo, os relatórios de fase, os planos com decisões travadas, um arquivo de ponto de retomada e treze memórias persistentes, cada uma com a decisão, o porquê e o modo de aplicar.

A consequência é que **a documentação deixou de ser subproduto e virou infraestrutura de continuidade**. Ela não era escrita para um leitor futuro hipotético; era escrita para o próprio agente na próxima sessão, e por isso tinha de ser precisa, datada e acionável. É essa exigência, e não uma preferência por documentação, que produziu a base de evidência que tornou este relato possível.

Um dado reforça a leitura. O projeto atravessou três gerações do modelo subjacente entre abril e julho, e o contrato de processo não mudou. Não é possível afirmar, sem as transcrições, que o comportamento do agente foi idêntico entre gerações; é possível afirmar que as regras que o governavam foram as mesmas e que os relatórios de fase mantiveram a estrutura. A estabilidade do método diante da troca de ferramenta é uma propriedade desejável em qualquer arranjo de trabalho com tecnologia que evolui rápido, e o contrato escrito é o que a garantiu aqui.

### 7.5. Os limites do agente avaliando a si mesmo

A auditoria de 07/06 encontrou dois problemas reais e corrigíveis. Mas ela também atribuiu uma nota ao próprio trabalho, e a nota não tem valor de evidência independente. O projeto reconheceu esse limite de forma prática ao desenhar a avaliação da busca semântica: o protocolo de avaliação separa colunas mecânicas, preenchidas automaticamente, de colunas de juízo, preenchidas por humanos, e inclui um bloco específico para medir o que chamou de viés de canonicidade, isto é, a tendência do modelo, treinado em texto majoritariamente canônico, a sub-ranquear justamente as obras de fronteira que a Análise Cognitiva quer reconhecer. O documento registra que, por isso, "a busca semântica não pode virar filtro de pertinência".

Esse mesmo limite se aplica a este relato. O inventário de decisões que o fundamenta foi produzido pelo agente a partir dos artefatos, e a redação foi assistida. As contagens são reprodutíveis por qualquer pessoa com acesso ao repositório e ao banco. As interpretações são dos autores humanos, que as revisaram, e são apresentadas como tal. O leitor deve tratar as primeiras como dado e as segundas como argumento.

### 7.6. O que é transferível e o que é local

Três elementos da experiência não dependem do domínio e podem ser adotados por outros grupos que trabalhem com agentes de código: o contrato de processo separado da especificação, com fases, parada obrigatória e relatório com seção de desvios; o ciclo parecer, decisão travada, fase e relatório, com a autorização explícita para o agente recomendar que não se implemente; e a regra de que dado curado por autoridade humana só muda por decisão humana, traduzida em restrições verificáveis pelo sistema.

Dois elementos são locais e não devem ser generalizados. A tensão entre rigor de revisão de escopo e permissividade da Análise Cognitiva é própria desse campo, e outro grupo pode querer exatamente o rigor que este desligou. E o perfil do grupo, uma turma de disciplina com prazos, explica reversões que um grupo de pesquisadores dedicados talvez não fizesse. O que se transfere é o mecanismo pelo qual as reversões foram governadas, não as reversões.

---

## 8. Considerações finais

A pergunta inicial era como governar um agente que constrói mais rápido do que o grupo consegue decidir. A resposta da experiência não é reduzir a velocidade do agente, e sim **colocar a decisão fora do código**: em um contrato de processo que impõe paradas, em pareceres que devolvem à instância certa o que não cabe ao implementador, e em documentos datados que travam a decisão antes de ela virar sistema. Feito isso, a velocidade deixa de ser um risco e passa a ser um instrumento, porque permite construir o que ainda não se compreende bem o suficiente para especificar, e aprender com o uso o que a especificação não sabia.

O relato tem lacunas que só podem ser preenchidas daqui em diante, e que se registram como agenda para quem repetir a experiência, inclusive este grupo:

- **Preservar as transcrições das sessões**, para medir prompts, retrabalho dentro de uma sessão e correções de rumo, que hoje são invisíveis.
- **Registrar início e fim de cada sessão no relatório de fase**, para confrontar as estimativas de esforço com o realizado.
- **Contar a taxa de aceitação**: quanto do que o agente propôs foi aceito, ajustado ou rejeitado. O inventário permite estimá-la para as decisões grandes, mas não para as pequenas.
- **Rotular a origem dos defeitos**, distinguindo mal-entendido de domínio de erro de implementação, porque a tese deste relato depende dessa distinção e ela foi feita retrospectivamente.
- **Ouvir os analistas**: 24 pessoas usam a plataforma e não há registro sistemático da sua percepção. Um questionário curto ao fim do ciclo atual é o passo seguinte natural.
- **Declarar a verificação humana**: quanto do código foi lido linha a linha pelo desenvolvedor antes de entrar em produção. O contrato não exigia essa declaração, e ela deveria constar do relatório de fase.

Uma decisão de desenho do estudo segue em aberto para a coordenação, e o relato a registra como está: no fluxo rigoroso, a triagem será feita por um revisor assistido por aprendizado ativo ou por dois revisores independentes. É uma decisão metodológica, não de implementação, e por isso não foi tomada pelo desenvolvedor nem pelo agente. Essa fronteira, mantida até a última linha, é o que este relato tem de mais importante a oferecer.

---

## Declaração de uso de inteligência artificial

Um agente de código baseado em modelos de linguagem da família Claude ⟦ajustar à política do veículo quanto a nomear o produto⟧ escreveu a maior parte do código da plataforma descrita, produziu os pareceres, a auditoria e a investigação de usabilidade citados, gerou o inventário de decisões a partir dos artefatos do repositório e auxiliou na redação deste texto. Todas as decisões de produto, de metodologia e de curadoria foram tomadas por pessoas, identificadas por papel na seção 3. As contagens apresentadas são reprodutíveis a partir do repositório e do banco de dados de produção. As interpretações são dos autores humanos, que revisaram integralmente o texto. Nenhuma referência bibliográfica foi incluída sem conferência humana da fonte. ⟦Confirmar a última frase antes da submissão.⟧

---

## Referências

⟦Todas a conferir. As marcadas [a levantar] ainda não existem na lista.⟧

- FLEISS, J. L. Measuring nominal scale agreement among many raters. *Psychological Bulletin*, v. 76, n. 5, p. 378-382, 1971. **[verificar]**
- FRÓES BURNHAM, T. Análise Cognitiva: aproximações iniciais para sua construção. In: ⟦obra, editora, ano, páginas⟧. **[verificar dados bibliográficos]**
- FRÓES BURNHAM, T. Análise Cognitiva: reconhecendo o antes irreconhecido. In: ⟦obra, editora, ano, páginas⟧. **[verificar dados bibliográficos]**
- LANDIS, J. R.; KOCH, G. G. The measurement of observer agreement for categorical data. *Biometrics*, v. 33, n. 1, p. 159-174, 1977. **[verificar]**
- NAESS, A.; CHRISTOPHERSEN, J. A.; KVALØ, K. *Democracy, ideology and objectivity*. Oslo: Oslo University Press, 1956. **[verificar]**
- TRICCO, A. C. et al. PRISMA Extension for Scoping Reviews (PRISMA-ScR): checklist and explanation. *Annals of Internal Medicine*, v. 169, n. 7, p. 467-473, 2018. **[verificar]**
- **[a levantar]** 2 a 3 estudos empíricos sobre produtividade e qualidade com assistentes ou agentes de código.
- **[a levantar]** 1 a 2 referências sobre *human-in-the-loop* e níveis de autonomia de agentes de software.
- **[a levantar]** 1 referência sobre a crítica ao *vibe coding*.
- **[a levantar]** 1 referência sobre *design-based research*, caso o veículo seja da área de Educação.

---

## Apêndice A — Inventário de decisões

⟦Exportar as tabelas D01 a D109 de `docs/artigo/inventario-de-decisoes.md` como material suplementar, se o veículo permitir. Caso contrário, disponibilizar em repositório público com identificador persistente e citar.⟧
