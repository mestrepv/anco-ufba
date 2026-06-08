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
    ArtigoAreaForm,
    ArtigoMetadadosForm,
    ComentarioCampoForm,
    IdentificadorLookupForm,
    ResenhaForm,
    RevisaoForm,
)
from .models import Analise, Artigo, ComentarioRevisao, Resenha, Revisao
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
        # Se o artigo (DOI/ISBN) já existe, reaproveita em vez de barrar com
        # "já existe": recupera (ou inicia) a análise do usuário e abre para
        # edição. Excluir uma análise não remove o Artigo — o DOI é único nele.
        from .services.crossref import normalizar_doi

        doi = normalizar_doi(request.POST.get("doi", ""))
        isbn = (request.POST.get("isbn") or "").strip()
        existente = None
        if doi:
            existente = Artigo.objects.filter(doi__iexact=doi).first()
        if existente is None and isbn:
            existente = Artigo.objects.filter(isbn=isbn).first()
        if existente is not None:
            analise, criada = Analise.objects.get_or_create(
                artigo=existente,
                analista=request.user,
                defaults={"status": Analise.Status.RASCUNHO},
            )
            if criada:
                messages.info(
                    request, "Este artigo já estava no acervo — análise iniciada para você."
                )
            else:
                messages.info(
                    request,
                    "Você já tinha uma análise deste artigo — abrindo para continuar.",
                )
            return redirect("editar_analise", analise_id=analise.pk)

        # Inclusão avulsa (Revisão ANCO): o analista pode cadastrar um artigo
        # próprio, analisá-lo e enviar à curadoria — fora do sorteio de projeto.
        # O acesso é pelo painel ANCO ("Artigo individual").
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
        contexto["erro"] = "Não reconheci o formato. Digite um DOI (10.xxxx/yyy) ou ISBN."
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
    if artigo.eh_legado and not _eh_admin(request.user):
        return HttpResponseForbidden(
            "O acervo histórico (legado) é pré-validado e não é analisável por analistas."
        )
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


PASSOS = [
    ("identificacao", "Identificação"),
    ("presenca", "Presença e pertinência"),
    ("estrutura", "Análise do artigo"),
]


# Abas do stepper: os 3 passos da análise + a resenha (entidade própria, em
# página dedicada). Hrefs absolutos para o stepper funcionar igual nas duas
# páginas (editar_analise e editar_resenha).
def _tabs(analise_pk: int) -> list[dict]:
    base = reverse("editar_analise", args=[analise_pk])
    tabs = [{"codigo": c, "label": label, "href": f"{base}?passo={c}"} for c, label in PASSOS]
    tabs.append(
        {
            "codigo": "resenha",
            "label": "Resenha crítica (opcional)",
            "href": reverse("editar_resenha", args=[analise_pk]),
        }
    )
    return tabs


def _stampar_edicao(analise: Analise, user) -> None:
    """Marca quem/quando editou. simple-history grava o detalhe."""
    analise.editado_em = timezone.now()
    analise.editado_por = user


@_exige_editor
def editar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Edição multipasso da análise (identificação / presença / estrutura).

    - Autor em rascunho/janela de 1h: pode editar.
    - Curador/admin: pode editar a qualquer tempo (grava stamp `editado_em` +
      `editado_por`, além do histórico via simple-history).

    A resenha crítica é editada à parte (ver `editar_resenha_view`).
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user
    eh_admin = _eh_admin(user)

    if not eh_admin and analise.analista_id != user.id:
        return HttpResponseForbidden("Apenas o analista autor (ou curador/admin) pode editar.")

    if analise.artigo.eh_legado and not eh_admin:
        return HttpResponseForbidden(
            "O acervo histórico (legado) é pré-validado e não é editável por analistas."
        )

    if not (eh_admin or analise.pode_ser_modificada):
        messages.info(request, "Esta análise não pode mais ser editada nesta janela.")
        return redirect("painel")

    passo = request.GET.get("passo", "identificacao")
    if passo not in dict(PASSOS):
        passo = "identificacao"

    form = None  # form da Análise (presença/estrutura)
    artigo_form = None  # form do Artigo (identificação: grande área)
    if passo == "identificacao":
        artigo_form = ArtigoAreaForm(request.POST or None, instance=analise.artigo)
    elif passo == "presenca":
        form = AnalisePresencaForm(request.POST or None, instance=analise)
    elif passo == "estrutura":
        form = AnaliseEstruturaForm(request.POST or None, instance=analise)

    def _avancar(passo_atual: str):
        ordem = [p for p, _ in PASSOS]
        idx = ordem.index(passo_atual)
        if idx + 1 < len(ordem):
            return redirect(f"{request.path}?passo={ordem[idx + 1]}")
        return redirect(request.path)

    if request.method == "POST" and artigo_form is not None and artigo_form.is_valid():
        artigo_form.save()  # atualiza a grande área do artigo
        messages.success(request, "Identificação salva.")
        return _avancar(passo)

    if request.method == "POST" and form is not None and form.is_valid():
        instance = form.save(commit=False)
        if eh_admin and analise.analista_id != user.id:
            _stampar_edicao(instance, user)  # edição administrativa: stamp
        instance.save()
        form.save_m2m()  # persiste epistemologia/teoria (M2M)
        messages.success(request, "Passo salvo.")
        return _avancar(passo)

    ordem = [p for p, _ in PASSOS]
    idx = ordem.index(passo)
    return render(
        request,
        "acervo/editar_analise.html",
        {
            "analise": analise,
            "passos": PASSOS,
            "tabs": _tabs(analise.pk),
            "passo_atual": passo,
            "passo_anterior": ordem[idx - 1] if idx > 0 else None,
            "passo_proximo": ordem[idx + 1] if idx + 1 < len(ordem) else None,
            "form": form,
            "artigo_form": artigo_form,
            "resenha": getattr(analise, "resenha", None),
            "eh_admin_edit": eh_admin and analise.analista_id != user.id,
            "campos_faltantes": analise.campos_faltantes_submissao(),
        },
    )


@_exige_editor
@require_POST
def autosave_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Auto-save: aceita POST com qualquer subset dos campos editaveis da análise,
    valida e persiste. Resposta JSON com timestamp do save.
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user
    eh_admin = _eh_admin(user)

    if not eh_admin and analise.analista_id != user.id:
        return HttpResponseForbidden("Voce nao pode salvar esta analise.")

    if not (eh_admin or analise.pode_ser_modificada):
        return JsonResponse(
            {"ok": False, "error": "Analise nao esta mais em rascunho."},
            status=400,
        )

    form = AnaliseCompletaForm(request.POST, instance=analise)

    if form.is_valid():
        instance = form.save(commit=False)
        if eh_admin and analise.analista_id != user.id:
            _stampar_edicao(instance, user)
        instance.save()
        form.save_m2m()  # persiste epistemologia/teoria (M2M)
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

    # Trava de servidor: só submete com todos os campos das abas 1–3 preenchidos.
    faltam = analise.campos_faltantes_submissao()
    if faltam:
        messages.error(
            request,
            "Preencha todos os campos antes de submeter. Faltam: " + ", ".join(faltam) + ".",
        )
        return redirect("editar_analise", analise_id=analise.pk)

    if request.method == "POST":
        analise.status = Analise.Status.SUBMETIDA
        analise.submetida_em = timezone.now()
        analise.save()
        from .tasks import notificar_analise_submetida

        notificar_analise_submetida(analise)
        messages.success(
            request,
            "Análise submetida. Aguardando aprovação da curadoria para entrar no acervo.",
        )
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
    messages.success(request, f'Análise excluída: "{titulo}…"')
    return redirect("painel")


# ---------------------------------------------------------------------------
# Resenha crítica: edição e submissão à revisão cega
# ---------------------------------------------------------------------------


def _get_resenha_editavel(request: HttpRequest, analise_id: int) -> Resenha:
    """
    Resenha (criando se necessário) da análise do autor logado.

    A resenha pode ser editada quando está em rascunho, ou após publicada
    (edição posterior reabre revisão cega). Levanta PermissionError caso o
    usuário não seja o autor.
    """
    analise = _get_analise_do_autor(request, analise_id)
    resenha, _ = Resenha.objects.get_or_create(analise=analise, defaults={"texto": ""})
    return resenha


@_exige_analista
@require_http_methods(["GET", "POST"])
def editar_resenha_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Autor edita o texto da resenha crítica (entidade própria)."""
    try:
        resenha = _get_resenha_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o autor pode editar a resenha.")

    if resenha.analise.artigo.eh_legado and not _eh_admin(request.user):
        return HttpResponseForbidden("O acervo histórico (legado) não é editável por analistas.")

    if resenha.status == Resenha.Status.EM_REVISAO:
        messages.info(request, "A resenha está em revisão cega e não pode ser editada agora.")
        return redirect("editar_analise", analise_id=analise_id)

    form = ResenhaForm(request.POST or None, instance=resenha)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Resenha salva.")
        return redirect("editar_resenha", analise_id=analise_id)

    return render(
        request,
        "acervo/editar_resenha.html",
        {
            "resenha": resenha,
            "analise": resenha.analise,
            "form": form,
            "tabs": _tabs(analise_id),
            "passo_atual": "resenha",
        },
    )


@_exige_analista
@require_POST
def submeter_resenha_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Submete a resenha para revisão cega (rascunho/revisada -> submetida)."""
    try:
        resenha = _get_resenha_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o autor pode submeter a resenha.")

    if not (resenha.texto or "").strip():
        messages.error(request, "Escreva a resenha antes de submetê-la.")
        return redirect("editar_resenha", analise_id=analise_id)
    if resenha.status in (Resenha.Status.SUBMETIDA, Resenha.Status.EM_REVISAO):
        messages.info(request, "A resenha já está em revisão.")
        return redirect("editar_resenha", analise_id=analise_id)

    resenha.status = Resenha.Status.SUBMETIDA
    resenha.submetida_em = timezone.now()
    resenha.save()  # signal dispara o sorteio cego
    messages.success(request, "Resenha submetida para revisão cega por pares.")
    return redirect("minhas_analises")


# ---------------------------------------------------------------------------
# Revisão cega por pares (da resenha)
# ---------------------------------------------------------------------------


# Campos expostos como pontos-de-âncora para comentário (revisão da resenha)
CAMPOS_ANCORAVEIS = [
    ("texto", "Resenha crítica"),
]


@_exige_analista
def minhas_revisoes_view(request: HttpRequest) -> HttpResponse:
    """Lista as revisoes pendentes (e historico) do usuario logado."""
    pendentes = (
        Revisao.objects.filter(revisor=request.user, concluido_em__isnull=True)
        .select_related("resenha__analise__artigo")
        .order_by("prazo_em")
    )
    concluidas = (
        Revisao.objects.filter(revisor=request.user, concluido_em__isnull=False)
        .select_related("resenha__analise__artigo")
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
    Tela de revisão cega de uma resenha crítica: parecer + comentários.

    A autoria nunca aparece (revisão sempre cega).
    """
    revisao = get_object_or_404(Revisao, pk=revisao_id)
    if revisao.revisor_id != request.user.id:
        return HttpResponseForbidden("Apenas o revisor sorteado pode acessar.")
    if revisao.concluido_em is not None:
        messages.info(request, "Esta revisão já foi concluída.")
        return redirect("minhas_revisoes")
    if revisao.resenha_id is None:
        return HttpResponseForbidden("Revisão sem resenha associada.")

    resenha = revisao.resenha
    analise = resenha.analise
    eh_cega = True

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

    # Monta tuplas (codigo, label, valor_atual_da_resenha, form_do_comentario)
    blocos = [
        (
            codigo,
            label,
            (getattr(resenha, codigo, "") or "").strip()
            if isinstance(getattr(resenha, codigo, ""), str)
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
            "resenha": resenha,
            "analise": analise,
            "eh_cega": eh_cega,
            "form": form,
            "blocos_comentarios": blocos,
        },
    )


# ---------------------------------------------------------------------------
# Curadoria: aprovação de análises e confirmação de resenhas revisadas
# ---------------------------------------------------------------------------


def _exige_curador(view):
    """Decorator: curador ou staff. Acesso à fila de curadoria."""

    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not _eh_admin(request.user):
            return HttpResponseForbidden("Apenas curadores acessam a curadoria.")
        return view(request, *args, **kwargs)

    return wrapper


@_exige_curador
def fila_curadoria_view(request: HttpRequest) -> HttpResponse:
    """Fila: análises submetidas + resenhas revisadas aguardando confirmação."""
    analises = (
        Analise.objects.filter(status=Analise.Status.SUBMETIDA)
        .select_related("artigo", "analista")
        .order_by("submetida_em", "id")
    )
    resenhas = (
        Resenha.objects.filter(status=Resenha.Status.REVISADA)
        .select_related("analise__artigo", "analise__analista")
        .order_by("submetida_em", "id")
    )
    return render(
        request,
        "acervo/curadoria.html",
        {"analises": analises, "resenhas": resenhas, "active_nav": "curadoria"},
    )


@_exige_curador
@require_POST
def aprovar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    from .tasks import notificar_publicacao_analise

    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status != Analise.Status.SUBMETIDA:
        messages.info(request, "Esta análise não está na fila de curadoria.")
        return redirect("fila_curadoria")
    agora = timezone.now()
    analise.status = Analise.Status.PUBLICADA
    analise.publicada_em = agora
    analise.aprovada_por = request.user
    analise.aprovada_em = agora
    analise.save()
    notificar_publicacao_analise(analise)
    messages.success(request, "Análise aprovada e publicada no acervo.")
    return redirect("fila_curadoria")


@_exige_curador
@require_POST
def devolver_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Pedir ajustes (-> rascunho) ou rejeitar (-> rejeitada), conforme `acao`."""
    from .tasks import notificar_analise_devolvida

    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status != Analise.Status.SUBMETIDA:
        messages.info(request, "Esta análise não está na fila de curadoria.")
        return redirect("fila_curadoria")
    motivo = (request.POST.get("motivo") or "").strip()
    rejeitar = request.POST.get("acao") == "rejeitar"
    analise.status = Analise.Status.REJEITADA if rejeitar else Analise.Status.RASCUNHO
    analise.motivo_curadoria = motivo
    analise.save()
    notificar_analise_devolvida(analise, motivo, rejeitada=rejeitar)
    messages.success(
        request,
        "Análise rejeitada." if rejeitar else "Análise devolvida para ajustes.",
    )
    return redirect("fila_curadoria")


@_exige_curador
@require_POST
def confirmar_resenha_view(request: HttpRequest, resenha_id: int) -> HttpResponse:
    from .tasks import notificar_resenha_publicada

    resenha = get_object_or_404(Resenha, pk=resenha_id)
    if resenha.status != Resenha.Status.REVISADA:
        messages.info(request, "Esta resenha não está aguardando confirmação.")
        return redirect("fila_curadoria")
    agora = timezone.now()
    resenha.status = Resenha.Status.PUBLICADA
    resenha.publicada_em = agora
    resenha.confirmada_por = request.user
    resenha.confirmada_em = agora
    resenha.save()
    notificar_resenha_publicada(resenha)
    messages.success(request, "Resenha confirmada e publicada no acervo.")
    return redirect("fila_curadoria")


@_exige_curador
@require_POST
def rejeitar_resenha_view(request: HttpRequest, resenha_id: int) -> HttpResponse:
    resenha = get_object_or_404(Resenha, pk=resenha_id)
    if resenha.status != Resenha.Status.REVISADA:
        messages.info(request, "Esta resenha não está aguardando confirmação.")
        return redirect("fila_curadoria")
    resenha.status = Resenha.Status.REJEITADA
    resenha.save()
    messages.success(request, "Resenha rejeitada.")
    return redirect("fila_curadoria")


# Status que podem ser despublicados (exclusão suave a partir do acervo público).
_STATUS_DESPUBLICAVEIS = (Analise.Status.PUBLICADA, Analise.Status.LEGADO)


@_exige_curador
@require_POST
def despublicar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """
    Exclusão suave: remove a análise do acervo público (status DESPUBLICADA),
    mantendo o registro no banco para eventual restauração. Admin/curador only.
    """
    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status not in _STATUS_DESPUBLICAVEIS:
        messages.info(request, "Esta análise não está publicada.")
        return redirect("pagina_analise", analise_id=analise.pk)
    analise.status_pre_despublicacao = analise.status
    analise.status = Analise.Status.DESPUBLICADA
    analise.despublicada_em = timezone.now()
    analise.despublicada_por = request.user
    analise.save(
        update_fields=[
            "status",
            "status_pre_despublicacao",
            "despublicada_em",
            "despublicada_por",
        ]
    )
    messages.success(
        request,
        "Análise despublicada — invisível no acervo público, mas preservada no "
        "banco. Você pode restaurá-la a qualquer momento.",
    )
    return redirect("pagina_analise", analise_id=analise.pk)


@_exige_curador
@require_POST
def restaurar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Restaura uma análise despublicada ao status que tinha antes."""
    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status != Analise.Status.DESPUBLICADA:
        messages.info(request, "Esta análise não está despublicada.")
        return redirect("pagina_analise", analise_id=analise.pk)
    analise.status = analise.status_pre_despublicacao or Analise.Status.PUBLICADA
    analise.status_pre_despublicacao = ""
    analise.despublicada_em = None
    analise.despublicada_por = None
    analise.save(
        update_fields=[
            "status",
            "status_pre_despublicacao",
            "despublicada_em",
            "despublicada_por",
        ]
    )
    messages.success(request, "Análise restaurada ao acervo público.")
    return redirect("pagina_analise", analise_id=analise.pk)
