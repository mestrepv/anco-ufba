"""Estatísticas do corpus ANCO — artigos × bases e acompanhamento da equipe."""

from __future__ import annotations

from collections import Counter

from django.db.models import F, Max


def estatisticas_por_base(projeto) -> list[dict]:
    """Quantos itens do corpus (não removidos) vieram de cada base.

    Um item pode vir de mais de uma fonte/base (é contado em cada uma).
    """
    itens = projeto.itens.filter(removido=False).prefetch_related("origem_fontes__base_consulta")
    contagem: Counter[str] = Counter()
    for it in itens:
        for f in it.origem_fontes.all():
            contagem[f.base_nome or "(sem base)"] += 1
    return sorted(
        ({"base": base, "n": n} for base, n in contagem.items()),
        key=lambda x: (-x["n"], x["base"]),
    )


def resumo(projeto) -> dict:
    """Totais do corpus do projeto."""
    itens = projeto.itens.filter(removido=False)
    anos = [i.ano for i in itens if i.ano]
    return {
        "total": itens.count(),
        "ano_min": min(anos) if anos else None,
        "ano_max": max(anos) if anos else None,
        "por_base": estatisticas_por_base(projeto),
    }


def relatorio_sorteio(projeto, sorteio) -> list[dict]:
    """Relatório de um sorteio: um bloco por analista com os artigos que recebeu.

    Cada artigo traz título, autor(es), base(s) de origem, DOI e URL — puxados do
    `ItemCorpus` do projeto (que guarda a proveniência), casando por artigo.
    Ordenado por nome do analista; artigos por título.
    """
    from .models import AtribuicaoANCO, ItemCorpus

    atribuicoes = AtribuicaoANCO.objects.filter(sorteio=sorteio).select_related(
        "analista", "artigo"
    )
    # Mapa artigo → ItemCorpus (com fontes) para a proveniência/base e os links.
    itens = (
        ItemCorpus.objects.filter(projeto=projeto, removido=False, artigo__isnull=False)
        .select_related("artigo")
        .prefetch_related("origem_fontes__base_consulta")
    )
    por_artigo: dict[int, object] = {}
    for it in itens:
        por_artigo.setdefault(it.artigo_id, it)

    grupos: dict[int, dict] = {}
    for at in atribuicoes:
        u = at.analista
        g = grupos.setdefault(
            u.pk,
            {"analista": u, "nome": u.nome_exibicao or u.email, "id": u.pk, "artigos": []},
        )
        it = por_artigo.get(at.artigo_id)
        art = at.artigo
        if it is not None:
            bases = sorted({f.base_nome or "(sem base)" for f in it.origem_fontes.all()})
            g["artigos"].append(
                {
                    "titulo": it.titulo or (art.titulo if art else ""),
                    "autores": it.autores or (art.autores if art else ""),
                    "base": ", ".join(bases),
                    "doi": it.doi or (art.doi if art else ""),
                    "url": it.link or (getattr(art, "link_acesso", "") if art else ""),
                }
            )
        else:  # atribuído mas item saiu do corpus — usa só o artigo
            g["artigos"].append(
                {
                    "titulo": art.titulo if art else "",
                    "autores": art.autores if art else "",
                    "base": "",
                    "doi": (art.doi if art else "") or "",
                    "url": getattr(art, "link_acesso", "") if art else "",
                }
            )

    linhas = list(grupos.values())
    for g in linhas:
        for a in g["artigos"]:
            a["doi_url"] = _doi_url(a["doi"])
        g["artigos"].sort(key=lambda a: a["titulo"].lower())
        g["n"] = len(g["artigos"])
    linhas.sort(key=lambda g: g["nome"].lower())
    return linhas


def _doi_url(doi: str) -> str:
    """URL resolvível do DOI. Aceita DOI puro (`10.x/...`) ou já como URL."""
    doi = (doi or "").strip()
    if not doi:
        return ""
    if doi.lower().startswith(("http://", "https://")):
        return doi
    return f"https://doi.org/{doi}"


def _contagem_status(analises) -> dict:
    """Contagem por status de um queryset de análises (rascunho/submetida/publicada)."""
    por_status = Counter(analises.values_list("status", flat=True))
    return {
        "rascunho": por_status.get("rascunho", 0),
        "submetida": por_status.get("submetida", 0),
        "publicada": por_status.get("publicada", 0),
        "total": sum(por_status.values()),
    }


def acompanhamento_membros(projeto) -> list[dict]:
    """Uma linha por membro do projeto: fontes, corpus, atribuições e análises.

    - *Análises no projeto* = análises do membro sobre artigos a ele atribuídos
      por sorteio deste projeto.
    - *Análises espontâneas* = demais análises do membro no acervo (fora das
      atribuições; exclui `legado`, que é importado e não trabalho do piloto).
    - *Última atividade* = evento mais recente entre importar fonte e
      criar/editar/submeter análise.
    """
    from apps.acervo.models import Analise

    from .models import AtribuicaoANCO

    linhas: list[dict] = []
    membros = projeto.membros.select_related("usuario").order_by("-papel", "usuario__email")
    for m in membros:
        u = m.usuario
        fontes = projeto.fontes.filter(criado_por=u)
        n_itens = (
            projeto.itens.filter(removido=False, origem_fontes__criado_por=u).distinct().count()
        )
        artigos_atribuidos = set(
            AtribuicaoANCO.objects.filter(sorteio__projeto=projeto, analista=u).values_list(
                "artigo_id", flat=True
            )
        )
        analises = Analise.objects.filter(analista=u).exclude(status=Analise.Status.LEGADO)
        no_projeto = _contagem_status(analises.filter(artigo_id__in=artigos_atribuidos))
        espontaneas = _contagem_status(analises.exclude(artigo_id__in=artigos_atribuidos))

        # Lista navegável: cada análise do membro, com link (o curador pode
        # pré-visualizar não-públicas em `pagina_analise`).
        analises_lista = [
            {
                "id": a.pk,
                "titulo": a.artigo.titulo,
                "status": a.status,
                "status_display": a.get_status_display(),
                "no_projeto": a.artigo_id in artigos_atribuidos,
                "quando": a.editado_em or a.submetida_em or a.criado_em,
            }
            for a in analises.select_related("artigo").order_by(
                "status", F("editado_em").desc(nulls_last=True), "-criado_em"
            )
        ]

        datas = [
            fontes.aggregate(x=Max("criado_em"))["x"],
            *analises.aggregate(
                a=Max("criado_em"), b=Max("submetida_em"), c=Max("editado_em")
            ).values(),
        ]
        datas = [d for d in datas if d]
        linhas.append(
            {
                "usuario": u,
                "papel": m.get_papel_display(),
                "eh_curador": m.papel == "curador",
                "n_fontes": fontes.count(),
                "n_itens": n_itens,
                "n_atribuidos": len(artigos_atribuidos),
                "no_projeto": no_projeto,
                "espontaneas": espontaneas,
                "analises_lista": analises_lista,
                "ultima_atividade": max(datas) if datas else None,
                "tem_atividade": bool(
                    fontes.exists() or no_projeto["total"] or espontaneas["total"]
                ),
            }
        )
    return linhas
