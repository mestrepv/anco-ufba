"""Views do app acervo: criacao e edicao de analises (Fase 3)."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    AnaliseCompletaForm,
    AnaliseEstruturaForm,
    AnalisePresencaForm,
    AnaliseResenhaForm,
    ArtigoForm,
    BuscaArtigoForm,
)
from .models import Analise, Artigo
from .services import (
    aplicar_resultado_no_artigo,
    capturar_snapshot_wayback,
    validar_link,
)


def _exige_analista(view):
    """Decorator: usuario logado E papel analista/curador."""

    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.eh_analista:
            return HttpResponseForbidden(
                "Apenas analistas podem acessar esta área. Solicite promoção."
            )
        return view(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Listagem de analises do proprio analista
# ---------------------------------------------------------------------------


@_exige_analista
def minhas_analises_view(request: HttpRequest) -> HttpResponse:
    analises = (
        Analise.objects.filter(analista=request.user)
        .select_related("artigo")
        .order_by("-criado_em")
    )
    return render(request, "acervo/minhas_analises.html", {"analises": analises})


# ---------------------------------------------------------------------------
# Buscar / cadastrar Artigo
# ---------------------------------------------------------------------------


@_exige_analista
def buscar_artigo_view(request: HttpRequest) -> HttpResponse:
    """
    Tela de busca por artigo. Mostra resultados ja no acervo e oferece
    cadastro de um novo. Resposta HTMX retorna so o painel de resultados.
    """
    form = BuscaArtigoForm(request.GET or None)
    resultados = []
    consulta = (request.GET.get("q") or "").strip()

    if consulta:
        resultados = list(
            Artigo.objects.filter(
                Q(doi__iexact=consulta)
                | Q(titulo__icontains=consulta)
                | Q(autores__icontains=consulta)
            ).order_by("-ano", "titulo")[:25]
        )

    template = (
        "acervo/_busca_resultados.html"
        if request.headers.get("HX-Request")
        else "acervo/buscar_artigo.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "resultados": resultados,
            "consulta": consulta,
            "tem_resultados": bool(resultados),
        },
    )


@_exige_analista
def cadastrar_artigo_view(request: HttpRequest) -> HttpResponse:
    """Cadastro de Artigo + criacao da Analise vinculada (status=rascunho)."""
    if request.method == "POST":
        form = ArtigoForm(request.POST)
        if form.is_valid():
            artigo = form.save(commit=False)
            artigo.eh_legado = False
            artigo.save()
            # Valida link e aplica resultado em artigo (silencioso em erro)
            try:
                resultado = validar_link(artigo.link_acesso)
                aplicar_resultado_no_artigo(artigo, resultado)
            except Exception:  # noqa: BLE001
                pass
            # Cria Analise vinculada para o analista corrente
            analise, _ = Analise.objects.get_or_create(
                artigo=artigo,
                analista=request.user,
                defaults={"status": Analise.Status.RASCUNHO},
            )
            messages.success(request, "Artigo cadastrado e análise iniciada.")
            return redirect("editar_analise", analise_id=analise.pk)
    else:
        form = ArtigoForm(initial={"doi": request.GET.get("doi", "")})

    return render(request, "acervo/cadastrar_artigo.html", {"form": form})


@_exige_analista
@require_POST
def capturar_snapshot_view(request: HttpRequest, artigo_id: int) -> HttpResponse:
    """Aciona Wayback Save Page Now para um Artigo existente. Resposta HTMX."""
    artigo = get_object_or_404(Artigo, pk=artigo_id)
    snapshot = capturar_snapshot_wayback(artigo, artigo.link_acesso)
    if snapshot is None:
        messages.warning(request, "Não foi possível capturar o snapshot agora.")
    else:
        messages.success(request, f"Snapshot capturado: {snapshot.url_wayback}")
    return render(
        request,
        "acervo/_snapshot_resultado.html",
        {"artigo": artigo, "snapshot": snapshot},
    )


@_exige_analista
def iniciar_analise_view(request: HttpRequest, artigo_id: int) -> HttpResponse:
    """Cria (ou recupera) Analise para o artigo selecionado."""
    artigo = get_object_or_404(Artigo, pk=artigo_id)
    analise, criada = Analise.objects.get_or_create(
        artigo=artigo,
        analista=request.user,
        defaults={"status": Analise.Status.RASCUNHO},
    )
    if criada:
        messages.success(request, "Análise iniciada.")
    return redirect("editar_analise", analise_id=analise.pk)


# ---------------------------------------------------------------------------
# Edicao multipasso da Analise
# ---------------------------------------------------------------------------


def _get_analise_editavel(request: HttpRequest, analise_id: int) -> Analise:
    """Devolve a analise se o usuario for o autor e ela ainda eh editavel."""
    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.analista_id != request.user.id:
        raise PermissionError("Voce nao eh o analista desta analise.")
    return analise


PASSOS = [
    ("identificacao", "Identificação"),
    ("presenca", "Presença e pertinência"),
    ("estrutura", "Estrutura do artigo"),
    ("resenha", "Resenha crítica (opcional)"),
]


@_exige_analista
def editar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Edicao da analise. Passo via parametro `?passo=...` (default: identificacao).
    Cada passo tem seu form proprio; auto-save em outro endpoint.
    """
    try:
        analise = _get_analise_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o analista autor pode editar.")

    if analise.status not in (Analise.Status.RASCUNHO,):
        messages.info(request, "Esta análise não está mais em rascunho.")
        return redirect("minhas_analises")

    passo = request.GET.get("passo", "identificacao")
    if passo not in dict(PASSOS):
        passo = "identificacao"

    form = None
    if passo == "presenca":
        form = AnalisePresencaForm(request.POST or None, instance=analise)
    elif passo == "estrutura":
        form = AnaliseEstruturaForm(request.POST or None, instance=analise)
    elif passo == "resenha":
        form = AnaliseResenhaForm(request.POST or None, instance=analise)

    if request.method == "POST" and form is not None and form.is_valid():
        form.save()
        messages.success(request, "Passo salvo.")
        # avanca para o proximo passo
        ordem = [p for p, _ in PASSOS]
        idx = ordem.index(passo)
        proximo = ordem[idx + 1] if idx + 1 < len(ordem) else "resenha"
        return redirect(f"{request.path}?passo={proximo}")

    return render(
        request,
        "acervo/editar_analise.html",
        {
            "analise": analise,
            "passos": PASSOS,
            "passo_atual": passo,
            "form": form,
        },
    )


@_exige_analista
@require_POST
def autosave_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Auto-save: aceita POST com qualquer subset dos campos editaveis,
    valida e persiste. Resposta JSON com timestamp do save.
    """
    try:
        analise = _get_analise_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o analista autor pode salvar.")

    if analise.status != Analise.Status.RASCUNHO:
        return JsonResponse(
            {"ok": False, "error": "Analise nao esta mais em rascunho."}, status=400
        )

    form = AnaliseCompletaForm(request.POST, instance=analise)
    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True, "salvo_em": timezone.now().strftime("%H:%M:%S")})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@_exige_analista
@require_http_methods(["GET", "POST"])
def submeter_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Submete a analise (rascunho -> submetida)."""
    try:
        analise = _get_analise_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o analista autor pode submeter.")

    if analise.status != Analise.Status.RASCUNHO:
        messages.info(request, "Esta análise já foi submetida ou publicada.")
        return redirect("minhas_analises")

    if request.method == "POST":
        analise.status = Analise.Status.SUBMETIDA
        analise.submetida_em = timezone.now()
        analise.save()
        if analise.tem_resenha:
            messages.success(
                request,
                "Análise submetida. Como ela inclui resenha crítica, passará "
                "também por revisão cega adicional.",
            )
        else:
            messages.success(request, "Análise submetida para revisão.")
        return redirect("minhas_analises")

    return render(request, "acervo/submeter_analise.html", {"analise": analise})
