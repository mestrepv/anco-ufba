"""
Views publicas do acervo (Fase 5).

- /acervo/                      — listagem facetada com FTS
- /artigo/<doi-slug>/           — pagina do artigo com analises publicadas
- /analise/<id>/                — pagina da analise (autoria visivel; cegos
  identificados como "Revisor cego A/B")
- /analise/<id>/historico/      — versoes (simple_history)
"""

from __future__ import annotations

from collections import Counter
from string import ascii_uppercase

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.acervo.models import Analise, Artigo, Revisao

from .services import (
    doi_to_slug,
    gerar_citacao_abnt,
    gerar_citacao_apa,
    slug_to_doi,
)

# Status que aparecem no acervo publico
STATUS_PUBLICOS = (Analise.Status.PUBLICADA, Analise.Status.LEGADO)


# ---------------------------------------------------------------------------
# Listagem com facetas (`/acervo/`)
# ---------------------------------------------------------------------------


_FACETAS = {
    # codigo (querystring) -> (campo de filtro, lookup, label legivel)
    "ano": ("artigo__ano", "exact", "Ano"),
    "base": ("artigo__base_consulta__nome", "exact", "Base de consulta"),
    "status": ("status", "exact", "Status"),
    "resenha": ("tem_resenha", "exact", "Tem resenha crítica"),
    "acesso_aberto": ("artigo__acesso_aberto", "exact", "Acesso aberto"),
    "link_status": ("artigo__link_status", "exact", "Status do link"),
}


def _aplicar_facetas(qs: QuerySet, params) -> QuerySet:
    """Aplica filtros das facetas selecionadas via querystring."""
    for codigo, (campo, _lookup, _label) in _FACETAS.items():
        valores = [v for v in params.getlist(codigo) if v]
        if not valores:
            continue
        # converte 'true'/'false' para bool quando o campo for booleano
        if codigo in ("resenha", "acesso_aberto"):
            valores = [v.lower() in ("true", "1", "sim", "s") for v in valores]
        qs = qs.filter(**{f"{campo}__in": valores})
    return qs


def _calcular_facetas(qs_base: QuerySet) -> dict[str, list[tuple[str, int]]]:
    """
    Conta ocorrencias por valor de cada faceta dentro do conjunto de
    resultados (sem ignorar a faceta "ja aplicada" — simplificacao
    aceitavel em volume baixo). Devolve dict de listas (valor, count).
    """
    facetas = {}
    # ano
    facetas["ano"] = list(
        qs_base.exclude(artigo__ano__isnull=True)
        .values_list("artigo__ano", flat=True)
        .order_by("-artigo__ano")
        .distinct()[:25]
    )
    facetas["ano_count"] = Counter(
        qs_base.exclude(artigo__ano__isnull=True).values_list("artigo__ano", flat=True)
    )
    facetas["base"] = Counter(
        qs_base.exclude(artigo__base_consulta__isnull=True).values_list(
            "artigo__base_consulta__nome", flat=True
        )
    ).most_common(15)
    facetas["status"] = Counter(qs_base.values_list("status", flat=True)).most_common()
    facetas["resenha_count"] = qs_base.filter(tem_resenha=True).count()
    facetas["acesso_aberto_count"] = qs_base.filter(artigo__acesso_aberto=True).count()
    return facetas


def listagem_view(request: HttpRequest) -> HttpResponse:
    qs = Analise.objects.filter(status__in=STATUS_PUBLICOS).select_related(
        "artigo", "artigo__base_consulta", "analista"
    )

    # Busca textual (FTS com unaccent — fallback para icontains se vazio)
    consulta = (request.GET.get("q") or "").strip()
    if consulta:
        vector = SearchVector(
            "artigo__titulo",
            "artigo__resumo",
            "objeto",
            "objetivo",
            "aspectos_relevantes",
            "definicao_extraida",
            "resenha_critica",
            config="portuguese",
        )
        query = SearchQuery(consulta, config="portuguese")
        qs = (
            qs.annotate(rank=SearchRank(vector, query))
            .filter(Q(rank__gt=0) | Q(artigo__doi__iexact=consulta))
            .order_by("-rank", "-criado_em")
        )
    else:
        qs = qs.order_by("-criado_em")

    # Aplica facetas
    qs = _aplicar_facetas(qs, request.GET)

    # Facetas (calculadas sobre conjunto base ja filtrado)
    facetas = _calcular_facetas(qs)

    # Paginacao
    paginator = Paginator(qs, 20)
    pagina = paginator.get_page(request.GET.get("page") or 1)

    # URL preservando facetas atuais (para troca de pagina)
    qs_dict = request.GET.copy()
    qs_dict.pop("page", None)
    querystring = qs_dict.urlencode()

    return render(
        request,
        "publico/listagem.html",
        {
            "consulta": consulta,
            "pagina": pagina,
            "facetas": facetas,
            "querystring": querystring,
            "facetas_aplicadas": {k: request.GET.getlist(k) for k in _FACETAS},
        },
    )


# ---------------------------------------------------------------------------
# Pagina do Artigo (`/artigo/<slug>/`)
# ---------------------------------------------------------------------------


def pagina_artigo_view(request: HttpRequest, doi_slug: str) -> HttpResponse:
    doi = slug_to_doi(doi_slug)
    artigo = get_object_or_404(Artigo, doi=doi)
    analises_publicas = (
        Analise.objects.filter(artigo=artigo, status__in=STATUS_PUBLICOS)
        .select_related("analista")
        .order_by("-publicada_em", "-criado_em")
    )
    snapshots = artigo.snapshots.order_by("-capturado_em")[:1]

    return render(
        request,
        "publico/artigo.html",
        {
            "artigo": artigo,
            "analises": analises_publicas,
            "snapshot_recente": snapshots[0] if snapshots else None,
        },
    )


# ---------------------------------------------------------------------------
# Pagina da Analise (`/analise/<id>/`)
# ---------------------------------------------------------------------------


def _revisoes_para_publico(analise: Analise) -> list[dict]:
    """
    Devolve lista de dicts {tipo, parecer, identificador} para exibir no acervo.

    - Estruturais: nome do revisor visivel.
    - Cegos: identificados como 'Revisor cego A', 'Revisor cego B', ...
    """
    qs = list(
        Revisao.objects.filter(analise=analise).select_related("revisor").order_by("tipo", "id")
    )
    cegas_idx = 0
    resultado = []
    for r in qs:
        if r.tipo == Revisao.Tipo.CEGA:
            identificador = f"Revisor cego {ascii_uppercase[cegas_idx]}"
            cegas_idx += 1
        else:
            identificador = (
                r.revisor.nome_exibicao or r.revisor.get_full_name() or r.revisor.username
            )
        resultado.append(
            {
                "tipo_label": r.get_tipo_display(),
                "parecer_label": r.get_parecer_display() if r.parecer else "—",
                "identificador": identificador,
                "concluido_em": r.concluido_em,
            }
        )
    return resultado


_CAMPOS_TEXTUAIS = (
    ("Aspectos relevantes", "aspectos_relevantes"),
    ("Definição extraída", "definicao_extraida"),
    ("Objeto", "objeto"),
    ("Objetivo", "objetivo"),
    ("Foco", "foco"),
    ("Metodologia", "metodologia"),
    ("Referenciais", "referenciais"),
    ("Resultados", "resultados"),
    ("Contexto de produção", "contexto_producao"),
    ("Observações", "observacoes"),
)


def pagina_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    analise = get_object_or_404(
        Analise.objects.select_related(
            "artigo", "artigo__base_consulta", "analista"
        ).prefetch_related("epistemologia", "teoria"),
        pk=analise_id,
    )
    if analise.status not in STATUS_PUBLICOS:
        raise Http404("Análise não publicada.")

    campos_textuais = [(label, getattr(analise, attr) or "") for label, attr in _CAMPOS_TEXTUAIS]

    return render(
        request,
        "publico/analise.html",
        {
            "analise": analise,
            "revisoes": _revisoes_para_publico(analise),
            "citacao_abnt": gerar_citacao_abnt(analise),
            "citacao_apa": gerar_citacao_apa(analise),
            "doi_slug": doi_to_slug(analise.artigo.doi),
            "campos_textuais": campos_textuais,
        },
    )


def historico_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status not in STATUS_PUBLICOS:
        raise Http404("Análise não publicada.")

    versoes = list(analise.history.order_by("-history_date")[:50])

    return render(
        request,
        "publico/historico.html",
        {
            "analise": analise,
            "versoes": versoes,
        },
    )
