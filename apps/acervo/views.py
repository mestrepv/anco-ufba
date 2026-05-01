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
    ArtigoMetadadosForm,
    BuscaArtigoForm,
    ComentarioCampoForm,
    IdentificadorLookupForm,
    RevisaoForm,
)
from .models import Analise, Artigo, ComentarioRevisao, Revisao
from .services import (
    aplicar_resultado_no_artigo,
    capturar_snapshot_wayback,
    lookup_doi,
    lookup_isbn,
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
    """
    Cadastro de Artigo (passo final) + criacao da Analise vinculada.

    GET: renderiza o formulário com IdentificadorLookupForm (passo 1) e
    ArtigoMetadadosForm (passo 3, pré-preenchido por querystring se vier
    de um lookup confirmado).

    POST: valida ArtigoMetadadosForm, cria Artigo + Analise (rascunho),
    valida link em background e redireciona para a edição da análise.
    """
    if request.method == "POST":
        form = ArtigoMetadadosForm(request.POST)
        if form.is_valid():
            artigo = form.save(commit=False)
            artigo.eh_legado = False
            artigo.save()
            # Valida link e aplica resultado no Artigo (silencioso em erro)
            try:
                resultado = validar_link(artigo.link_acesso)
                aplicar_resultado_no_artigo(artigo, resultado)
            except Exception:  # noqa: BLE001
                pass
            analise, _ = Analise.objects.get_or_create(
                artigo=artigo,
                analista=request.user,
                defaults={"status": Analise.Status.RASCUNHO},
            )
            messages.success(request, "Artigo cadastrado e análise iniciada.")
            return redirect("editar_analise", analise_id=analise.pk)
        lookup_form = IdentificadorLookupForm()
    else:
        # GET pode trazer dados de um lookup confirmado em campos initial
        initial: dict[str, object] = {}
        for chave in (
            "doi",
            "isbn",
            "tipo_publicacao",
            "titulo",
            "titulo_periodico",
            "ano",
            "volume",
            "numero",
            "pagina_inicial",
            "pagina_final",
            "autores",
            "palavras_chaves",
            "resumo",
            "link_acesso",
        ):
            valor = request.GET.get(chave, "")
            if valor:
                initial[chave] = valor
        form = ArtigoMetadadosForm(initial=initial)
        lookup_form = IdentificadorLookupForm(
            initial={"identificador": request.GET.get("doi") or request.GET.get("isbn") or ""}
        )

    return render(
        request,
        "acervo/cadastrar_artigo.html",
        {"form": form, "lookup_form": lookup_form},
    )


@_exige_analista
def lookup_identificador_view(request: HttpRequest) -> HttpResponse:
    """
    Endpoint HTMX que consulta Crossref ou OpenLibrary a partir de um DOI
    ou ISBN e retorna um cartão de pré-visualização dos metadados.

    Querystring:
    - `id`: o identificador digitado (DOI, ISBN, URL doi.org, etc.)
    - `tipo` (opcional): "doi" ou "isbn" para forçar a rota — quando ausente,
      `IdentificadorLookupForm` detecta automaticamente.
    """
    form = IdentificadorLookupForm(request.GET or None)
    contexto: dict[str, object] = {
        "identificador_raw": (request.GET.get("id") or "").strip(),
        "encontrado": False,
        "erro": "",
        "dados": {},
        "tipo": "vazio",
        "ja_no_acervo": False,
        "analise_existente_id": None,
    }

    if not contexto["identificador_raw"]:
        return render(request, "acervo/_preview_metadados.html", contexto)

    # Re-monta o form com o `id` da querystring sob o nome correto
    form_data = {"identificador": contexto["identificador_raw"]}
    form = IdentificadorLookupForm(data=form_data)
    if not form.is_valid():
        contexto["erro"] = "Identificador inválido."
        return render(request, "acervo/_preview_metadados.html", contexto)

    classificado = form.cleaned_data["identificador"]
    contexto["tipo"] = classificado["tipo"]

    tipo_forcado = (request.GET.get("tipo") or "").strip().lower()
    if tipo_forcado in {"doi", "isbn"}:
        contexto["tipo"] = tipo_forcado

    if contexto["tipo"] == "doi":
        resultado = lookup_doi(classificado["valor"] or contexto["identificador_raw"])
    elif contexto["tipo"] == "isbn":
        resultado = lookup_isbn(classificado["valor"] or contexto["identificador_raw"])
    else:
        contexto["erro"] = (
            "Não reconheci o formato. Digite um DOI (10.xxxx/yyy) ou ISBN."
        )
        return render(request, "acervo/_preview_metadados.html", contexto)

    contexto["encontrado"] = resultado.encontrado
    contexto["erro"] = resultado.erro
    contexto["dados"] = resultado.dados

    # Verifica se o artigo já está cadastrado no acervo
    if resultado.encontrado:
        valor = classificado["valor"]
        if contexto["tipo"] == "doi":
            existente = Artigo.objects.filter(doi=valor).first()
        else:
            existente = Artigo.objects.filter(isbn=valor).first()
        if existente:
            contexto["ja_no_acervo"] = True
            analise = (
                Analise.objects.filter(artigo=existente, analista=request.user)
                .order_by("-criado_em")
                .first()
            )
            if analise:
                contexto["analise_existente_id"] = analise.pk

    return render(request, "acervo/_preview_metadados.html", contexto)


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


# ---------------------------------------------------------------------------
# Revisao por pares (Fase 4)
# ---------------------------------------------------------------------------


# Campos da Analise expostos como pontos-de-ancora para comentario
CAMPOS_ANCORAVEIS = [
    ("objeto", "Objeto"),
    ("objetivo", "Objetivo"),
    ("foco", "Foco"),
    ("metodologia", "Metodologia"),
    ("resultados", "Resultados"),
    ("aspectos_relevantes", "Aspectos relevantes"),
    ("definicao_extraida", "Definição extraída"),
    ("resenha_critica", "Resenha crítica"),
]


@_exige_analista
def minhas_revisoes_view(request: HttpRequest) -> HttpResponse:
    """Lista as revisoes pendentes (e historico) do usuario logado."""
    pendentes = (
        Revisao.objects.filter(revisor=request.user, concluido_em__isnull=True)
        .select_related("analise__artigo")
        .order_by("prazo_em")
    )
    concluidas = (
        Revisao.objects.filter(revisor=request.user, concluido_em__isnull=False)
        .select_related("analise__artigo")
        .order_by("-concluido_em")[:20]
    )
    return render(
        request,
        "acervo/minhas_revisoes.html",
        {"pendentes": pendentes, "concluidas": concluidas},
    )


@_exige_analista
@require_http_methods(["GET", "POST"])
def revisar_view(request: HttpRequest, revisao_id: int) -> HttpResponse:
    """
    Tela de revisao: form de parecer + comentarios ancorados por campo.

    Quando a revisao eh CEGA, autoria do analista nao aparece em nenhum
    lugar — nem no contexto do template, nem no historico de versoes.
    """
    revisao = get_object_or_404(Revisao, pk=revisao_id)
    if revisao.revisor_id != request.user.id:
        return HttpResponseForbidden("Apenas o revisor sorteado pode acessar.")
    if revisao.concluido_em is not None:
        messages.info(request, "Esta revisão já foi concluída.")
        return redirect("minhas_revisoes")

    analise = revisao.analise
    eh_cega = revisao.tipo == Revisao.Tipo.CEGA

    if request.method == "POST":
        form = RevisaoForm(request.POST, instance=revisao)
        comentarios_existentes = {
            c.campo: c for c in ComentarioRevisao.objects.filter(revisao=revisao)
        }
        comentarios_forms = [
            ComentarioCampoForm(
                request.POST,
                prefix=f"c_{campo}",
                initial={"campo": campo},
            )
            for campo, _ in CAMPOS_ANCORAVEIS
        ]
        if form.is_valid() and all(c.is_valid() for c in comentarios_forms):
            revisao = form.save(commit=False)
            revisao.concluido_em = timezone.now()
            revisao.save()

            # persiste comentarios nao-vazios
            for cf in comentarios_forms:
                campo = cf.cleaned_data["campo"]
                texto = (cf.cleaned_data.get("texto") or "").strip()
                existente = comentarios_existentes.get(campo)
                if texto and existente:
                    existente.texto = texto
                    existente.save()
                elif texto:
                    ComentarioRevisao.objects.create(revisao=revisao, campo=campo, texto=texto)
                elif existente and not texto:
                    existente.delete()

            messages.success(request, "Revisão enviada. Obrigado!")
            return redirect("minhas_revisoes")
    else:
        form = RevisaoForm(instance=revisao)
        comentarios_existentes = {
            c.campo: c.texto for c in ComentarioRevisao.objects.filter(revisao=revisao)
        }
        comentarios_forms = [
            ComentarioCampoForm(
                prefix=f"c_{campo}",
                initial={
                    "campo": campo,
                    "texto": comentarios_existentes.get(campo, ""),
                },
            )
            for campo, _ in CAMPOS_ANCORAVEIS
        ]

    # Monta tuplas (codigo, label, valor_atual_da_analise, form_do_comentario)
    blocos = [
        (
            codigo,
            label,
            (getattr(analise, codigo, "") or "").strip()
            if isinstance(getattr(analise, codigo, ""), str)
            else "",
            cf,
        )
        for (codigo, label), cf in zip(CAMPOS_ANCORAVEIS, comentarios_forms, strict=True)
    ]

    return render(
        request,
        "acervo/revisar.html",
        {
            "revisao": revisao,
            "analise": analise,
            "eh_cega": eh_cega,
            "form": form,
            "blocos_comentarios": blocos,
        },
    )
