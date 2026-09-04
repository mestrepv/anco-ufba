"""
Views publicas do acervo (Fase 5).

- /acervo/                      — listagem facetada com FTS
- /artigo/<doi-slug>/           — pagina do artigo com analises publicadas
- /analise/<id>/                — pagina da analise (autoria visivel; cegos
  identificados como "Revisor cego A/B")
- /analise/<id>/historico/      — versoes (simple_history)
"""

from __future__ import annotations

import datetime
from collections import Counter
from string import ascii_uppercase

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from apps.acervo.models import Analise, Artigo, Resenha, Revisao

from .schema import jsonld, schema_analise, schema_artigo
from .services import (
    doi_to_slug,
    gerar_citacao_abnt,
    gerar_citacao_apa,
    slug_to_doi,
)

User = get_user_model()

# Status que aparecem no acervo publico
STATUS_PUBLICOS = (Analise.Status.PUBLICADA, Analise.Status.LEGADO)

_MESES_PT = {
    1: "jan.",
    2: "fev.",
    3: "mar.",
    4: "abr.",
    5: "mai.",
    6: "jun.",
    7: "jul.",
    8: "ago.",
    9: "set.",
    10: "out.",
    11: "nov.",
    12: "dez.",
}


def _fmt_data(d: datetime.date | datetime.datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime.datetime):
        d = d.date()
    return f"{d.day} {_MESES_PT[d.month]} {d.year}"


# ---------------------------------------------------------------------------
# Vitrine (`/`)
# ---------------------------------------------------------------------------


def vitrine_view(request: HttpRequest) -> HttpResponse:
    analises_count = Analise.objects.filter(status__in=STATUS_PUBLICOS).count()
    # Pesquisadores que de fato publicaram (autores de analise PUBLICADA/LEGADO).
    pesquisadores_count = (
        User.objects.filter(analises__status__in=STATUS_PUBLICOS).distinct().count()
    )
    # Analistas cadastrados na equipe — mesma definicao do diretorio /equipe.
    # Cresce a cada cadastro, independente de publicacao.
    analistas_count = User.objects.equipe_publica().count()
    bases_count = (
        Artigo.objects.filter(
            analises__status__in=STATUS_PUBLICOS,
            base_consulta__isnull=False,
        )
        .values("base_consulta")
        .distinct()
        .count()
    )
    ano_agg = Artigo.objects.filter(
        analises__status__in=STATUS_PUBLICOS,
        ano__isnull=False,
    ).aggregate(min_ano=Min("ano"), max_ano=Max("ano"))
    recentes_qs = (
        Analise.objects.filter(status__in=STATUS_PUBLICOS)
        .select_related("artigo", "analista", "resenha")
        .order_by("criado_em", "id")[:5]
    )
    recentes = [
        {
            "analise": a,
            "data_fmt": _fmt_data(a.publicada_em or a.criado_em),
        }
        for a in recentes_qs
    ]
    return render(
        request,
        "vitrine.html",
        {
            "analises_count": analises_count,
            "analistas_count": analistas_count,
            "pesquisadores_count": pesquisadores_count,
            "bases_count": bases_count,
            "min_ano": ano_agg["min_ano"],
            "max_ano": ano_agg["max_ano"],
            "recentes": recentes,
            "hoje_fmt": _fmt_data(datetime.date.today()),
        },
    )


# ---------------------------------------------------------------------------
# Listagem com facetas (`/acervo/`)
# ---------------------------------------------------------------------------


_FACETAS = {
    # codigo (querystring) -> (campo de filtro, lookup, label legivel)
    "base": ("artigo__base_consulta__nome", "exact", "Base de consulta"),
    "status": ("status", "exact", "Status"),
    "resenha": ("resenha", "exact", "Tem resenha crítica"),
    "acesso_aberto": ("artigo__acesso_aberto", "exact", "Acesso aberto"),
    "link_status": ("artigo__link_status", "exact", "Status do link"),
}

# Resenha visível no acervo público = publicada/legado.
RESENHA_PUBLICA_Q = Q(resenha__status__in=Resenha.PUBLICAS)


def _aplicar_facetas(qs: QuerySet, params) -> QuerySet:
    """Aplica filtros das facetas selecionadas via querystring."""
    for codigo, (campo, _lookup, _label) in _FACETAS.items():
        valores = [v for v in params.getlist(codigo) if v]
        if not valores:
            continue
        if codigo == "resenha":
            # "true" => tem resenha pública; só "false" => não tem.
            quer = [v.lower() in ("true", "1", "sim", "s") for v in valores]
            qs = qs.filter(RESENHA_PUBLICA_Q) if any(quer) else qs.exclude(RESENHA_PUBLICA_Q)
            continue
        if codigo == "acesso_aberto":
            valores = [v.lower() in ("true", "1", "sim", "s") for v in valores]
        qs = qs.filter(**{f"{campo}__in": valores})
    return qs


def _parse_int_param(params, key: str) -> int | None:
    try:
        return int(params.get(key))
    except (TypeError, ValueError):
        return None


def _aplicar_filtro_ano(qs: QuerySet, params) -> QuerySet:
    """Filtro de range de ano via ano_min / ano_max."""
    lo = _parse_int_param(params, "ano_min")
    hi = _parse_int_param(params, "ano_max")
    if lo is not None:
        qs = qs.filter(artigo__ano__gte=lo)
    if hi is not None:
        qs = qs.filter(artigo__ano__lte=hi)
    return qs


def _calcular_facetas(qs_base: QuerySet) -> dict[str, list[tuple[str, int]]]:
    """
    Conta ocorrencias por valor de cada faceta dentro do conjunto de
    resultados (sem ignorar a faceta "ja aplicada" — simplificacao
    aceitavel em volume baixo). Devolve dict de listas (valor, count).
    """
    facetas = {}
    facetas["base"] = Counter(
        qs_base.exclude(artigo__base_consulta__isnull=True).values_list(
            "artigo__base_consulta__nome", flat=True
        )
    ).most_common(15)
    # (codigo, rótulo amigável, contagem) — value usa o código; exibe o label.
    _status_labels = dict(Analise.Status.choices)
    facetas["status"] = [
        (codigo, _status_labels.get(codigo, codigo), n)
        for codigo, n in Counter(qs_base.values_list("status", flat=True)).most_common()
    ]
    facetas["resenha_count"] = qs_base.filter(RESENHA_PUBLICA_Q).count()
    facetas["acesso_aberto_count"] = qs_base.filter(artigo__acesso_aberto=True).count()
    return facetas


def _busca_semantica(consulta: str, qs_base: QuerySet) -> list[dict]:
    """
    Busca por similaridade de vetores. Retorna lista de dicts com
    analise + score (0-100) ordenada por similaridade decrescente.
    Máximo 50 resultados conforme spec §6.2.1.
    """
    from pgvector.django import CosineDistance

    from apps.busca_semantica.embeddings import embed_query

    vec = embed_query(consulta)
    if vec is None:
        return []

    resultados = (
        qs_base.exclude(embedding__isnull=True)
        .annotate(distancia=CosineDistance("embedding", vec))
        .order_by("distancia")[:50]
    )

    return [
        {
            "analise": r,
            "score": round((1 - float(r.distancia)) * 100),
        }
        for r in resultados
    ]


@ratelimit(key="ip", rate="60/m", method=["GET"], block=False)
def listagem_view(request: HttpRequest) -> HttpResponse:
    qs_base = Analise.objects.filter(status__in=STATUS_PUBLICOS).select_related(
        "artigo", "artigo__base_consulta", "analista", "resenha"
    )

    consulta = (request.GET.get("q") or "").strip()
    modo = request.GET.get("modo", "textual")
    if modo not in ("textual", "semantico"):
        modo = "textual"

    # Range global de anos (limites do slider) — calcula uma vez sobre o universo público
    ano_agg = Artigo.objects.filter(
        analises__status__in=STATUS_PUBLICOS,
        ano__isnull=False,
    ).aggregate(min_ano=Min("ano"), max_ano=Max("ano"))
    ano_min_global = ano_agg["min_ano"]
    ano_max_global = ano_agg["max_ano"]

    # Aplica facetas (sem ano) e depois o filtro de ano
    qs_filtrado = _aplicar_facetas(qs_base, request.GET)
    qs_filtrado = _aplicar_filtro_ano(qs_filtrado, request.GET)

    ano_aplicado_min = _parse_int_param(request.GET, "ano_min")
    ano_aplicado_max = _parse_int_param(request.GET, "ano_max")
    ano_filtrado = ano_aplicado_min is not None or ano_aplicado_max is not None

    # Atalhos pré-calculados (rótulo + faixa real, ancorado no max do acervo)
    ano_presets = []
    if ano_min_global is not None:
        for n_anos in (5, 10):
            lo = max(ano_min_global, ano_max_global - n_anos + 1)
            ano_presets.append({"label": f"{n_anos} anos", "lo": lo, "hi": ano_max_global})

    resultados_semanticos: list[dict] = []
    servico_indisponivel = False
    pagina = None

    if modo == "semantico" and consulta:
        from apps.busca_semantica.embeddings import service_available

        if service_available():
            resultados_semanticos = _busca_semantica(consulta, qs_filtrado)
        else:
            servico_indisponivel = True
            modo = "textual"  # degradação graciosa: cai para textual

    if modo == "textual":
        qs = qs_filtrado
        if consulta:
            vector = SearchVector(
                "artigo__titulo",
                "artigo__resumo",
                "objeto",
                "objetivo",
                "aspectos_relevantes",
                "definicao_extraida",
                config="portuguese_unaccent",
            )
            query = SearchQuery(consulta, config="portuguese_unaccent")
            # Filtra pelo operador @@ (match booleano), não por rank > 0:
            # ts_rank pode retornar 1e-20 (não-zero) para não-matches em queries
            # multi-palavra, fazendo `rank > 0` deixar passar tudo. O annotate
            # `search=vector` traduz `filter(search=query)` em `vector @@ query`.
            qs = (
                qs.annotate(search=vector, rank=SearchRank(vector, query))
                .filter(Q(search=query) | Q(artigo__doi__iexact=consulta))
                .order_by("-rank", "-artigo__ano", "artigo__titulo")
            )
        else:
            qs = qs.order_by("-artigo__ano", "artigo__titulo", "id")

        paginator = Paginator(qs, 20)
        pagina = paginator.get_page(request.GET.get("page") or 1)

    # Facetas calculadas sobre o conjunto base filtrado (sem busca textual aplicada)
    facetas = _calcular_facetas(qs_filtrado)

    qs_dict = request.GET.copy()
    qs_dict.pop("page", None)
    querystring = qs_dict.urlencode()

    facetas_aplicadas = {k: request.GET.getlist(k) for k in _FACETAS}
    n_filtros_ativos = sum(len(v) for v in facetas_aplicadas.values()) + (1 if ano_filtrado else 0)
    ordenar_label = "relevância" if consulta else "ano de publicação"

    # Universo da busca semântica (análises com vetor estrutural).
    # Calculado só quando o modo está ativo, para evitar query desnecessária.
    n_analises_semanticas = (
        qs_base.exclude(embedding__isnull=True).count() if modo == "semantico" else 0
    )

    return render(
        request,
        "publico/listagem.html",
        {
            "consulta": consulta,
            "modo": modo,
            "pagina": pagina,
            "resultados_semanticos": resultados_semanticos,
            "servico_indisponivel": servico_indisponivel,
            "facetas": facetas,
            "querystring": querystring,
            "facetas_aplicadas": facetas_aplicadas,
            "n_filtros_ativos": n_filtros_ativos,
            "ordenar_label": ordenar_label,
            "active_nav": "acervo",
            "ano_min_global": ano_min_global,
            "ano_max_global": ano_max_global,
            "ano_aplicado_min": ano_aplicado_min,
            "ano_aplicado_max": ano_aplicado_max,
            "ano_presets": ano_presets,
            "ano_filtrado": ano_filtrado,
            "n_analises_semanticas": n_analises_semanticas,
        },
    )


# ---------------------------------------------------------------------------
# Planilha completa (`/acervo/planilha/`) — visao tabular com filtros por coluna
# ---------------------------------------------------------------------------


def _linha_planilha(a: Analise) -> dict:
    """Serializa uma Analise publica em uma linha JSON-friendly da grade."""
    artigo = a.artigo
    epistemologia = "; ".join(t.nome for t in a.epistemologia.all())
    teoria = "; ".join(t.nome for t in a.teoria.all())
    return {
        "id": a.pk,
        "url": reverse("pagina_analise", args=[a.pk]),
        "ano": artigo.ano,
        "titulo": artigo.titulo,
        "periodico": artigo.titulo_periodico or "",
        "autores": artigo.autores or "",
        "base": (artigo.base_consulta.nome if artigo.base_consulta else ""),
        "area": artigo.area or "",
        "doi": (artigo.doi or "") if not (artigo.doi or "").startswith("legacy:") else "",
        "link_artigo": artigo.link_acesso or artigo.link_acesso_alternativo or "",
        "epistemologia": epistemologia,
        "teoria": teoria,
        "analista": (a.analista.nome_exibicao or a.analista.username),
        "tem_resenha": bool(getattr(a, "resenha", None) and a.resenha.status in Resenha.PUBLICAS),
        "acesso_aberto": bool(artigo.acesso_aberto),
        "status": a.get_status_display(),
        "publicada_em": (a.publicada_em or a.criado_em).date().isoformat(),
    }


def planilha_view(request: HttpRequest) -> HttpResponse:
    qs = (
        Analise.objects.filter(status__in=STATUS_PUBLICOS)
        .select_related("artigo", "artigo__base_consulta", "analista", "resenha")
        .prefetch_related("epistemologia", "teoria")
        .order_by("-publicada_em", "-criado_em")
    )
    linhas = [_linha_planilha(a) for a in qs]
    return render(
        request,
        "publico/planilha.html",
        {
            "linhas": linhas,
            "total": len(linhas),
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
        .select_related("analista", "resenha")
        .order_by("-publicada_em", "-criado_em")
    )
    snapshots = artigo.snapshots.order_by("-capturado_em")[:1]

    # Análise do usuário logado para este artigo (se já existir), para
    # decidir entre "Escrever resenha" vs "Continuar minha análise".
    minha_analise = None
    if request.user.is_authenticated and request.user.eh_analista:
        minha_analise = Analise.objects.filter(artigo=artigo, analista=request.user).first()

    return render(
        request,
        "publico/artigo.html",
        {
            "artigo": artigo,
            "analises": analises_publicas,
            "snapshot_recente": snapshots[0] if snapshots else None,
            "jsonld": jsonld(schema_artigo(artigo)),
            "minha_analise": minha_analise,
        },
    )


# ---------------------------------------------------------------------------
# Pagina da Analise (`/analise/<id>/`)
# ---------------------------------------------------------------------------


def _revisoes_para_publico(resenha) -> list[dict]:
    """
    Revisões cegas da resenha, identificadas como 'Revisor cego A/B/...'
    (autoria sempre anonimizada).
    """
    if resenha is None:
        return []
    qs = list(Revisao.objects.filter(resenha=resenha, concluido_em__isnull=False).order_by("id"))
    resultado = []
    for idx, r in enumerate(qs):
        resultado.append(
            {
                "identificador": f"Revisor cego {ascii_uppercase[idx]}",
                "parecer_label": r.get_parecer_display() if r.parecer else "—",
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
            "artigo", "artigo__base_consulta", "analista", "resenha"
        ).prefetch_related("epistemologia", "teoria"),
        pk=analise_id,
    )
    # Admin/curador podem pré-visualizar análises não públicas (submetida,
    # despublicada, etc.) para curar; o público só vê as publicadas/legado.
    pode_curar = request.user.is_authenticated and (
        request.user.is_staff or getattr(request.user, "eh_curador", False)
    )
    nao_publica = analise.status not in STATUS_PUBLICOS
    if nao_publica and not pode_curar:
        raise Http404("Análise não publicada.")
    despublicada = analise.status == Analise.Status.DESPUBLICADA
    submetida = analise.status == Analise.Status.SUBMETIDA

    campos_textuais = [(label, getattr(analise, attr) or "") for label, attr in _CAMPOS_TEXTUAIS]

    link_obra = analise.artigo.link_acesso or analise.artigo.link_acesso_alternativo or ""

    # Resenha crítica só aparece quando publicada/legado.
    resenha = getattr(analise, "resenha", None)
    resenha_publica = resenha if (resenha and resenha.status in Resenha.PUBLICAS) else None

    # Proveniência: o artigo foi selecionado via triagem PRISMA-ScR?
    # (reverse de apps.triagem.RegistroTriagem.artigo; "incluido" = status incluído)
    proveniencia_triagem = analise.artigo.registros_triagem.filter(status="incluido").exists()

    # Sinaliza se há resenha pública em outras análises do mesmo artigo.
    outras_com_resenha = (
        Analise.objects.filter(
            artigo=analise.artigo,
            status__in=STATUS_PUBLICOS,
            resenha__status__in=Resenha.PUBLICAS,
        )
        .exclude(pk=analise.pk)
        .exists()
    )

    return render(
        request,
        "publico/analise.html",
        {
            "analise": analise,
            "resenha_publica": resenha_publica,
            "revisoes": _revisoes_para_publico(resenha_publica),
            "citacao_abnt": gerar_citacao_abnt(analise),
            "citacao_apa": gerar_citacao_apa(analise),
            "doi_slug": doi_to_slug(analise.artigo.doi),
            "campos_textuais": campos_textuais,
            "link_obra": link_obra,
            "publicada_fmt": _fmt_data(analise.publicada_em or analise.criado_em),
            "outras_com_resenha": outras_com_resenha,
            "proveniencia_triagem": proveniencia_triagem,
            "active_nav": "acervo",
            "jsonld": jsonld(schema_analise(analise)),
            "pode_curar": pode_curar,
            "despublicada": despublicada,
            "submetida": submetida,
            "nao_publica": nao_publica,
            "status_label": analise.get_status_display(),
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


# ---------------------------------------------------------------------------
# Paginas institucionais (Fase 7)
# ---------------------------------------------------------------------------


def pagina_sobre_view(request: HttpRequest) -> HttpResponse:
    return render(request, "publico/sobre.html")


def pagina_equipe_view(request: HttpRequest) -> HttpResponse:
    """
    Diretório dinâmico de analistas.

    Aparece quem tem `papel ∈ {analista, curador}` e perfil mínimo preenchido
    (nome + vínculo). Curador é cargo interno — o publico ve todos como
    analistas. Contas do legado (sintéticas) e contas de serviço ficam fora.

    A definicao de quem entra vive em `User.objects.equipe_publica()`, para
    nao divergir da contagem exibida na home.
    """
    analistas = User.objects.equipe_publica().order_by("papel", "nome_exibicao", "username")
    return render(
        request,
        "publico/equipe.html",
        {
            "active_nav": "equipe",
            "analistas": analistas,
            "total": analistas.count(),
        },
    )


def _distribuicao(base_qs: QuerySet, campo: str, rotulo_fn, ordem) -> dict:
    """
    Conta artigos distintos por `campo` no acervo público.

    `rotulo_fn(valor)` traduz o valor cru para um rótulo legível.
    `ordem` é a chave de `.order_by()` aplicada ao agregado.
    Retorna {"itens": [{rotulo, n, pct}], "total", "maximo"}.
    """
    linhas = base_qs.values(campo).annotate(n=Count("id", distinct=True)).order_by(ordem)
    total = sum(linha["n"] for linha in linhas)
    maximo = max((linha["n"] for linha in linhas), default=0)
    itens = [
        {
            "rotulo": rotulo_fn(linha[campo]),
            "n": linha["n"],
            "pct": round(linha["n"] * 100 / total, 1) if total else 0,
        }
        for linha in linhas
    ]
    return {"itens": itens, "total": total, "maximo": maximo}


def pagina_estatisticas_view(request: HttpRequest) -> HttpResponse:
    """
    Estatísticas do acervo público: distribuição dos artigos por ano,
    por base de consulta e por idioma. Considera apenas artigos com ao
    menos uma análise publicada/legado (mesmo universo do acervo público).
    """
    base_qs = Artigo.objects.filter(analises__status__in=STATUS_PUBLICOS)
    total_artigos = base_qs.distinct().count()

    idiomas = dict(Artigo.Idioma.choices)

    por_ano = _distribuicao(
        base_qs,
        "ano",
        lambda v: str(v) if v else "Sem ano informado",
        "ano",
    )
    por_base = _distribuicao(
        base_qs,
        "base_consulta__nome",
        lambda v: v or "Base não informada",
        "-n",
    )
    por_idioma = _distribuicao(
        base_qs,
        "idioma",
        lambda v: idiomas.get(v, "Não informado") if v else "Não informado",
        "-n",
    )

    return render(
        request,
        "publico/estatisticas.html",
        {
            "active_nav": "estatisticas",
            "total_artigos": total_artigos,
            "por_ano": por_ano,
            "por_base": por_base,
            "por_idioma": por_idioma,
        },
    )


def pagina_termos_view(request: HttpRequest) -> HttpResponse:
    return render(request, "publico/termos.html")


def pagina_privacidade_view(request: HttpRequest) -> HttpResponse:
    return render(request, "publico/privacidade.html")


# ---------------------------------------------------------------------------
# SEO: robots.txt e sitemap.xml
# ---------------------------------------------------------------------------


def robots_txt_view(request: HttpRequest) -> HttpResponse:
    base = request.build_absolute_uri("/").rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /accounts/\n"
        "Disallow: /cadastro/\n"
        "Disallow: /acervo-analista/\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_view(request: HttpRequest) -> HttpResponse:
    """Sitemap XML simples — lista todas as paginas publicas indexaveis."""
    base = request.build_absolute_uri("/").rstrip("/")
    urls: list[tuple[str, str | None]] = [
        (f"{base}/", None),
        (f"{base}/acervo/", None),
        (f"{base}/acervo/planilha/", None),
        (f"{base}/sobre/", None),
        (f"{base}/equipe/", None),
        (f"{base}/termos/", None),
        (f"{base}/privacidade/", None),
    ]
    # Analises publicadas/legado
    for analise in Analise.objects.filter(status__in=STATUS_PUBLICOS).only(
        "pk", "publicada_em", "criado_em"
    ):
        url = f"{base}/analise/{analise.pk}/"
        lastmod = (analise.publicada_em or analise.criado_em).date().isoformat()
        urls.append((url, lastmod))
    # Artigos com analises publicas
    for artigo in (
        Artigo.objects.filter(
            analises__status__in=STATUS_PUBLICOS,
        )
        .only("pk", "doi", "atualizado_em")
        .distinct()
    ):
        slug = doi_to_slug(artigo.doi)
        urls.append((f"{base}/artigo/{slug}/", artigo.atualizado_em.date().isoformat()))

    body = ['<?xml version="1.0" encoding="UTF-8"?>']
    body.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url, lastmod in urls:
        body.append("<url>")
        body.append(f"<loc>{url}</loc>")
        if lastmod:
            body.append(f"<lastmod>{lastmod}</lastmod>")
        body.append("</url>")
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")
