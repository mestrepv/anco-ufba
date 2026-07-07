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


# Situação da análise de cada artigo sorteado (rótulo + ordem de exibição).
# Unifica o acompanhamento no relatório do sorteio: dá para ver, por analista,
# o que falta, o que está em andamento e o que já foi entregue.
ESTADOS_ARTIGO = {
    "nada": {"rotulo": "A fazer", "ordem": 0},
    "andamento": {"rotulo": "Em andamento", "ordem": 1},
    "submetida": {"rotulo": "Enviada", "ordem": 2},
    "publicada": {"rotulo": "Publicada", "ordem": 3},
}


def _estado_artigo(status) -> str:
    """Classifica o status da Analise do analista para um artigo sorteado."""
    from apps.acervo.models import Analise

    if status is None:
        return "nada"
    if status == Analise.Status.RASCUNHO:
        return "andamento"
    if status == Analise.Status.REJEITADA:
        return "andamento"  # devolvida pela curadoria: volta a ser trabalho
    if status == Analise.Status.SUBMETIDA:
        return "submetida"
    return "publicada"  # publicada / legado


def relatorio_sorteio(projeto, sorteio) -> list[dict]:
    """Relatório de um sorteio: um bloco por analista com os artigos que recebeu.

    Cada artigo traz título, autor(es), base(s), DOI, link de acesso e a
    **situação da análise** (a fazer / em andamento / enviada / publicada). Cada
    analista traz um resumo de **progresso** (concluídas de total). Unifica
    sorteio + acompanhamento numa tela só. Ordenado por nome do analista; artigos
    pela situação (o que falta primeiro), depois título.
    """
    from apps.acervo.models import Analise

    from .models import AtribuicaoANCO, ItemCorpus

    atribuicoes = AtribuicaoANCO.objects.filter(sorteio=sorteio).select_related(
        "analista", "artigo"
    )
    # Status da análise por (analista, artigo) — uma consulta para toda a tela.
    status_por = {
        (a["analista_id"], a["artigo_id"]): a["status"]
        for a in Analise.objects.filter(
            analista__in={at.analista_id for at in atribuicoes},
            artigo__in={at.artigo_id for at in atribuicoes},
        ).values("analista_id", "artigo_id", "status")
    }
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
        estado = _estado_artigo(status_por.get((u.pk, at.artigo_id)))
        if it is not None:
            bases = sorted({f.base_nome or "(sem base)" for f in it.origem_fontes.all()})
            g["artigos"].append(
                {
                    "titulo": it.titulo or (art.titulo if art else ""),
                    "autores": it.autores or (art.autores if art else ""),
                    "base": ", ".join(bases),
                    "doi": it.doi or (art.doi if art else ""),
                    "url": it.link or (getattr(art, "link_acesso", "") if art else ""),
                    "estado": estado,
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
                    "estado": estado,
                }
            )

    linhas = list(grupos.values())
    for g in linhas:
        for a in g["artigos"]:
            a["doi_url"] = _doi_url(a["doi"])
            # Link de acesso ao texto — prioriza a URL do artigo/tese; só cai no
            # resolvedor de DOI quando não há URL própria. É o que o analista abre.
            a["acesso_url"] = (a["url"] or "").strip() or a["doi_url"]
            a["acesso_host"] = _host(a["acesso_url"])
            a["acesso_via_doi"] = not (a["url"] or "").strip() and bool(a["doi_url"])
            a["estado_rotulo"] = ESTADOS_ARTIGO[a["estado"]]["rotulo"]
        # O que falta primeiro; depois por título.
        g["artigos"].sort(key=lambda a: (ESTADOS_ARTIGO[a["estado"]]["ordem"], a["titulo"].lower()))
        g["n"] = len(g["artigos"])
        # Progresso do analista: concluída = enviada à curadoria ou publicada.
        cont = Counter(a["estado"] for a in g["artigos"])
        concluidas = cont["submetida"] + cont["publicada"]
        g["progresso"] = {
            "total": g["n"],
            "concluidas": concluidas,
            "andamento": cont["andamento"],
            "a_fazer": cont["nada"],
            "pct": round(100 * concluidas / g["n"]) if g["n"] else 0,
            # estado geral do analista, p/ o ponto colorido e a ordenação
            "estado": (
                "concluido"
                if g["n"] and concluidas == g["n"]
                else "andamento"
                if (concluidas or cont["andamento"])
                else "nada"
            ),
        }
    # Ordena os analistas: quem tem trabalho parado primeiro (a fazer / em
    # andamento), depois quem concluiu; dentro de cada grupo, por nome.
    _ordem_estado = {"nada": 0, "andamento": 1, "concluido": 2}
    linhas.sort(key=lambda g: (_ordem_estado[g["progresso"]["estado"]], g["nome"].lower()))
    return linhas


def _doi_url(doi: str) -> str:
    """URL resolvível do DOI. Aceita DOI puro (`10.x/...`) ou já como URL."""
    doi = (doi or "").strip()
    if not doi:
        return ""
    if doi.lower().startswith(("http://", "https://")):
        return doi
    return f"https://doi.org/{doi}"


def _host(url: str) -> str:
    """Domínio de uma URL (sem `www.`), para rótulo compacto do link de acesso."""
    from urllib.parse import urlparse

    try:
        net = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return net[4:] if net.startswith("www.") else net


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
