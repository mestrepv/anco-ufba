"""Estatísticas do corpus ANCO — artigos × bases e acompanhamento da equipe."""

from __future__ import annotations

from collections import Counter

from django.db.models import Max


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
                "ultima_atividade": max(datas) if datas else None,
                "tem_atividade": bool(
                    fontes.exists() or no_projeto["total"] or espontaneas["total"]
                ),
            }
        )
    return linhas
