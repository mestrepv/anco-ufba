"""Views do app acervo: criacao e edicao de analises (Fase 3)."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    AnaliseCompletaForm,
    AnaliseEstruturaForm,
    AnalisePresencaForm,
    AnaliseResenhaForm,
    ArtigoMetadadosForm,
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


def _exige_editor(view):
    """Decorator: analista/curador OU staff. Usado em editar/autosave."""

    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not (request.user.eh_analista or request.user.is_staff):
            return HttpResponseForbidden(
                "Apenas analistas, curadores ou administradores podem editar."
            )
        return view(request, *args, **kwargs)

    return wrapper


def _eh_admin(user) -> bool:
    """Curador ou staff — pode editar qualquer analise a qualquer tempo."""
    return user.is_staff or getattr(user, "eh_curador", False)


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
# Cadastrar Artigo (entrada unica do fluxo de contribuicao)
# ---------------------------------------------------------------------------


def buscar_artigo_view(request: HttpRequest) -> HttpResponse:
    """Compat: a tela de busca foi unificada em `cadastrar_artigo`."""
    return redirect("cadastrar_artigo")


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

    # 1) Banco local primeiro: se o artigo ja existe no acervo, evita chamada
    # externa e exibe direto o aviso "arquivo existente, deseja revisar?".
    valor = classificado["valor"]
    existente: Artigo | None = None
    if valor and contexto["tipo"] == "doi":
        existente = Artigo.objects.filter(doi=valor).first()
    elif valor and contexto["tipo"] == "isbn":
        existente = Artigo.objects.filter(isbn=valor).first()

    if existente is not None:
        contexto["encontrado"] = True
        contexto["ja_no_acervo"] = True
        contexto["artigo_existente"] = existente
        contexto["dados"] = {
            "titulo": existente.titulo,
            "autores_str": existente.autores or "",
            "ano": existente.ano or "",
            "doi": existente.doi or "",
            "isbn": existente.isbn or "",
            "periodico": existente.titulo_periodico or "",
            "resumo": existente.resumo or "",
            "ja_no_acervo": True,
        }
        analise = (
            Analise.objects.filter(artigo=existente, analista=request.user)
            .order_by("-criado_em")
            .first()
        )
        if analise:
            contexto["analise_existente_id"] = analise.pk
        return render(request, "acervo/_preview_metadados.html", contexto)

    # 2) Nao esta no acervo: consulta fonte externa (Crossref / OpenLibrary).
    if contexto["tipo"] == "doi":
        resultado = lookup_doi(valor or contexto["identificador_raw"])
    elif contexto["tipo"] == "isbn":
        resultado = lookup_isbn(valor or contexto["identificador_raw"])
    else:
        contexto["erro"] = (
            "Não reconheci o formato. Digite um DOI (10.xxxx/yyy) ou ISBN."
        )
        return render(request, "acervo/_preview_metadados.html", contexto)

    contexto["encontrado"] = resultado.encontrado
    # Copia para nao mutar o objeto cacheado em Redis pelo lookup_doi/lookup_isbn
    contexto["dados"] = dict(resultado.dados) if resultado.dados else {}
    contexto["erro"] = resultado.erro

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
    """
    Cria (ou recupera) Analise para o artigo selecionado.

    Aceita `?passo=<nome>` para abrir o editor diretamente em um passo
    específico (ex: `?passo=resenha` quando o analista quer só registrar
    uma resenha crítica sem preencher a grade toda).
    """
    artigo = get_object_or_404(Artigo, pk=artigo_id)
    analise, criada = Analise.objects.get_or_create(
        artigo=artigo,
        analista=request.user,
        defaults={"status": Analise.Status.RASCUNHO},
    )
    if criada:
        messages.success(request, "Análise iniciada.")
    url = reverse("editar_analise", args=[analise.pk])
    passo = request.GET.get("passo")
    if passo:
        url = f"{url}?passo={passo}"
    return redirect(url)


# ---------------------------------------------------------------------------
# Edicao multipasso da Analise
# ---------------------------------------------------------------------------


def _get_analise_do_autor(request: HttpRequest, analise_id: int) -> Analise:
    """Devolve a analise se o usuario for o autor (sem checar editabilidade)."""
    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.analista_id != request.user.id:
        raise PermissionError("Voce nao eh o analista desta analise.")
    return analise


def _escopo_edicao(request: HttpRequest, analise_id: int) -> tuple[Analise, str]:
    """
    Devolve `(analise, escopo)` onde `escopo` e:

    - `"full"`     — pode editar todos os campos (autor em rascunho/janela,
                     ou curador/admin a qualquer tempo).
    - `"resenha"`  — pode editar apenas a resenha critica (autor de uma
                     analise ja publicada/aprovada/legado).

    Levanta `PermissionError` se o usuario nao puder editar nem a resenha.
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user

    if _eh_admin(user):
        return analise, "full"

    if analise.analista_id != user.id:
        raise PermissionError("Voce nao eh o analista desta analise.")

    if analise.pode_ser_modificada:
        return analise, "full"

    if analise.pode_editar_resenha_pos_publicacao:
        return analise, "resenha"

    raise PermissionError("Analise nao pode mais ser editada nesta janela.")


PASSOS = [
    ("identificacao", "Identificação"),
    ("presenca", "Presença e pertinência"),
    ("estrutura", "Estrutura do artigo"),
    ("resenha", "Resenha crítica (opcional)"),
]


def _stampar_edicao(analise: Analise, user) -> None:
    """Marca quem/quando editou. simple-history grava o detalhe."""
    analise.editado_em = timezone.now()
    analise.editado_por = user


@_exige_editor
def editar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Edicao da analise. Escopo varia conforme papel/estado:

    - Autor em rascunho/janela: todos os passos.
    - Autor de analise publicada/aprovada/legado: apenas resenha.
      Salvar a resenha volta status para `submetida` e dispara revisao cega.
    - Curador/admin: todos os campos a qualquer tempo. Salvar gravara stamp
      `editado_em` + `editado_por` (alem do historico via simple-history).
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user
    eh_admin = _eh_admin(user)

    if not eh_admin and analise.analista_id != user.id:
        return HttpResponseForbidden(
            "Apenas o analista autor (ou curador/admin) pode editar."
        )

    if eh_admin:
        escopo = "full"
    elif analise.pode_ser_modificada:
        escopo = "full"
    elif analise.pode_editar_resenha_pos_publicacao:
        escopo = "resenha"
    else:
        messages.info(
            request,
            "Esta análise não pode mais ser editada nesta janela.",
        )
        return redirect("painel")

    eh_autor_pos_publicacao = (not eh_admin) and escopo == "resenha"

    # Quando escopo eh "resenha", forca o passo. Quando "full", passo livre.
    if escopo == "resenha":
        passo = "resenha"
    else:
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
        instance = form.save(commit=False)

        if eh_admin and analise.analista_id != user.id:
            # Edicao administrativa: stamp obrigatorio.
            _stampar_edicao(instance, user)

        if eh_autor_pos_publicacao:
            # Adicionar/editar resenha em analise ja publicada -> revisao cega.
            _stampar_edicao(instance, user)
            instance.status = Analise.Status.SUBMETIDA
            instance.submetida_em = timezone.now()
            instance.save()
            # Dispara sorteio so de cegas (estruturais ja foram feitas).
            from django_q.tasks import async_task
            async_task(
                "apps.acervo.tasks.task_sortear_cegos_adicional", instance.pk
            )
            messages.success(
                request,
                "Resenha salva. A análise voltou para revisão cega antes de "
                "ser republicada.",
            )
            return redirect("pagina_analise", analise_id=analise.pk)

        instance.save()
        messages.success(request, "Passo salvo.")

        if escopo == "full":
            ordem = [p for p, _ in PASSOS]
            idx = ordem.index(passo)
            proximo = ordem[idx + 1] if idx + 1 < len(ordem) else "resenha"
            return redirect(f"{request.path}?passo={proximo}")
        return redirect(request.path)

    return render(
        request,
        "acervo/editar_analise.html",
        {
            "analise": analise,
            "passos": PASSOS,
            "passo_atual": passo,
            "form": form,
            "escopo": escopo,
            "eh_admin_edit": eh_admin and analise.analista_id != user.id,
            "eh_autor_pos_publicacao": eh_autor_pos_publicacao,
        },
    )


@_exige_editor
@require_POST
def autosave_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Auto-save: aceita POST com qualquer subset dos campos editaveis,
    valida e persiste. Resposta JSON com timestamp do save.

    Respeita o escopo: em escopo "resenha", so persiste `resenha_critica`.
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user
    eh_admin = _eh_admin(user)

    if not eh_admin and analise.analista_id != user.id:
        return HttpResponseForbidden("Voce nao pode salvar esta analise.")

    if eh_admin:
        escopo = "full"
    elif analise.pode_ser_modificada:
        escopo = "full"
    elif analise.pode_editar_resenha_pos_publicacao:
        escopo = "resenha"
    else:
        return JsonResponse(
            {"ok": False, "error": "Analise nao esta mais em rascunho."},
            status=400,
        )

    if escopo == "resenha":
        form = AnaliseResenhaForm(request.POST, instance=analise)
    else:
        form = AnaliseCompletaForm(request.POST, instance=analise)

    if form.is_valid():
        instance = form.save(commit=False)
        if eh_admin and analise.analista_id != user.id:
            _stampar_edicao(instance, user)
        instance.save()
        return JsonResponse({"ok": True, "salvo_em": timezone.now().strftime("%H:%M:%S")})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@_exige_analista
@require_http_methods(["GET", "POST"])
def submeter_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Submete a analise (rascunho -> submetida)."""
    try:
        analise = _get_analise_do_autor(request, analise_id)
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


@_exige_analista
@require_POST
def excluir_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Exclui a análise se a revisão ainda não começou (rascunho ou submetida
    sem revisões criadas). Só o analista autor pode excluir.
    """
    try:
        analise = _get_analise_do_autor(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o analista autor pode excluir.")

    if not analise.pode_ser_modificada:
        messages.error(
            request,
            "Esta análise não pode mais ser excluída — janela de 1h após o "
            "envio já encerrou ou a revisão começou.",
        )
        return redirect("painel")

    titulo = analise.artigo.titulo[:80]
    analise.delete()
    messages.success(request, f"Análise excluída: \"{titulo}…\"")
    return redirect("painel")


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
