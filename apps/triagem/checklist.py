"""Checklist PRISMA-ScR (Tricco et al., Ann Intern Med 2018) — 22 itens.

Cada item indica **onde o AnCo já ajuda** (valor automático/atalho) ou se é de
relato do autor no manuscrito. Itens 12 e 16 (avaliação crítica) são opcionais
em revisões de escopo.
"""

from __future__ import annotations

# (secao, num, titulo, descricao, anco, link, opcional)
ITENS = [
    ("Título", 1, "Título",
     "Identifique o relato como uma revisão de escopo.",
     "No manuscrito.", None, False),
    ("Resumo", 2, "Resumo estruturado",
     "Resumo estruturado (contexto, objetivos, critérios, fontes, métodos, resultados, conclusões).",
     "No manuscrito.", None, False),
    ("Introdução", 3, "Justificativa",
     "Justificativa da revisão no contexto do que já se sabe.",
     "No manuscrito.", None, False),
    ("Introdução", 4, "Objetivos",
     "Pergunta(s) e objetivos explícitos (elementos PCC: população/conceito/contexto).",
     "Pergunta de pesquisa do protocolo.", "triagem_protocolo", False),
    ("Métodos", 5, "Protocolo e registro",
     "Existência do protocolo, onde acessá-lo e o registro (nº/URL).",
     "Protocolo versionado + registro externo (OSF).", "triagem_protocolo", False),
    ("Métodos", 6, "Critérios de elegibilidade",
     "Características usadas como critérios (anos, idioma, tipo) e a justificativa.",
     "Critérios de inclusão/exclusão + filtros (período, idiomas, tipos).", "triagem_protocolo", False),
    ("Métodos", 7, "Fontes de informação",
     "Todas as fontes da busca (bases, cobertura) e a data da busca mais recente.",
     "Importações: bases e datas.", "triagem_painel", False),
    ("Métodos", 8, "Estratégia de busca",
     "Estratégia eletrônica completa de ≥1 base, com limites, de forma reproduzível.",
     "String de busca + filtros por importação.", "triagem_painel", False),
    ("Métodos", 9, "Seleção das fontes",
     "Processo de seleção (triagem e elegibilidade).",
     "Triagem por ≥2 revisores independentes, consenso/desempate, concordância (κ).", "triagem_prisma", False),
    ("Métodos", 10, "Processo de extração (charting)",
     "Métodos de extração (formulário calibrado/testado; independente ou em duplicata).",
     "Matriz AnCo (formulário estruturado da análise).", None, False),
    ("Métodos", 11, "Itens de dados",
     "Variáveis para as quais se buscaram dados, com definições.",
     "Campos da Matriz AnCo (objeto, objetivo, foco, epistemologia, teoria…).", None, False),
    ("Métodos", 12, "Avaliação crítica das fontes",
     "Se feita: justificativa, métodos e uso na síntese.",
     "Opcional em revisões de escopo.", None, True),
    ("Métodos", 13, "Síntese dos resultados",
     "Métodos de tratamento e sumarização dos dados extraídos.",
     "Acervo + estatísticas + busca facetada/semântica.", "pagina_estatisticas", False),
    ("Resultados", 14, "Seleção das fontes (fluxo)",
     "Nº de fontes triadas, avaliadas e incluídas, com razões de exclusão por etapa (fluxograma).",
     "Fluxograma PRISMA (contagens por etapa + razões).", "triagem_prisma", False),
    ("Resultados", 15, "Características das fontes",
     "Características extraídas de cada fonte, com citações.",
     "Páginas das análises (citação ABNT/APA).", None, False),
    ("Resultados", 16, "Avaliação crítica nas fontes",
     "Se feita: dados da avaliação crítica (ver item 12).",
     "Opcional em revisões de escopo.", None, True),
    ("Resultados", 17, "Resultados por fonte",
     "Dados extraídos relevantes às perguntas, por fonte incluída.",
     "Cada análise publicada no acervo.", None, False),
    ("Resultados", 18, "Síntese dos resultados",
     "Sumarização dos resultados relacionada às perguntas/objetivos.",
     "Estatísticas + mapa do acervo.", "pagina_estatisticas", False),
    ("Discussão", 19, "Síntese das evidências",
     "Resumo dos principais resultados, ligação às perguntas e relevância.",
     "No manuscrito.", None, False),
    ("Discussão", 20, "Limitações",
     "Limitações do processo de revisão de escopo.",
     "No manuscrito.", None, False),
    ("Discussão", 21, "Conclusões",
     "Interpretação geral, implicações e próximos passos.",
     "No manuscrito.", None, False),
    ("Financiamento", 22, "Financiamento",
     "Fontes de financiamento da revisão e papel dos financiadores.",
     "No manuscrito.", None, False),
]


def secoes() -> list[dict]:
    """Itens agrupados por seção, na ordem do PRISMA-ScR."""
    grupos: dict[str, list] = {}
    ordem: list[str] = []
    for secao, num, titulo, descricao, anco, link, opcional in ITENS:
        if secao not in grupos:
            grupos[secao] = []
            ordem.append(secao)
        grupos[secao].append(
            {"num": num, "titulo": titulo, "descricao": descricao,
             "anco": anco, "link": link, "opcional": opcional}
        )
    return [{"secao": s, "itens": grupos[s]} for s in ordem]
