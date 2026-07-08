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


def _projeto_anco_do_analista(user, artigo=None):
    """Resolve o projeto ANCO onde este analista trabalha (worklist de sorteados).

    Preferência: a atribuição do próprio `artigo` (quando dado); senão, a
    atribuição mais recente do analista. Retorna `ProjetoANCO` ou `None` — o
    fluxo ANCO vive em `apps/anco`, não na triagem PRISMA.
    """
    from apps.anco.models import AtribuicaoANCO

    qs = AtribuicaoANCO.objects.filter(analista=user).select_related("sorteio__projeto")
    if artigo is not None:
        atrib = qs.filter(artigo=artigo).order_by("-sorteio_id").first()
        if atrib:
            return atrib.sorteio.projeto
    atrib = qs.order_by("-sorteio_id").first()
    return atrib.sorteio.projeto if atrib else None


@_exige_analista
def minhas_analises_view(request: HttpRequest) -> HttpResponse:
    analises = (
        Analise.objects.filter(analista=request.user)
        .select_related("artigo")
        .order_by("-criado_em")
    )
    projeto_anco = _projeto_anco_do_analista(request.user)
    return render(
        request,
        "acervo/minhas_analises.html",
        {"analises": analises, "projeto_anco": projeto_anco},
    )


# ---------------------------------------------------------------------------
# Cadastrar Artigo (entrada unica do fluxo de contribuicao)
# ---------------------------------------------------------------------------


def buscar_artigo_view(request: HttpRequest) -> HttpResponse:
    """Compat: a tela de busca foi unificada em `cadastrar_artigo`."""
    return redirect("cadastrar_artigo")


def _projeto_corpus(request: HttpRequest):
    """Projeto ANCO de destino do "Artigo individual" (slug em ?projeto=/POST).

    Só retorna o projeto se for ANCO ativo e o usuário for membro (ou admin);
    caso contrário, o cadastro segue o fluxo avulso (inicia a própria análise).
    """
    slug = (request.GET.get("projeto") or request.POST.get("projeto") or "").strip()
    if not slug:
        return None
    from apps.anco.models import ProjetoANCO

    projeto = ProjetoANCO.objects.filter(slug=slug, arquivado=False).first()
    if projeto is None:
        return None
    if projeto.eh_membro(request.user) or _eh_admin(request.user):
        return projeto
    return None


# Lista de artigos adicionados na sessão do analista, por projeto (slug). Serve de
# "progresso" visível no loop de "Artigo individual": some só ao concluir. Ver
# cadastrar_artigo_view.
_SESSAO_ADD = "anco_sessao_add"
_SESSAO_ADD_MAX = 60


def _sessao_add_lista(request: HttpRequest, slug: str) -> list[dict]:
    return (request.session.get(_SESSAO_ADD) or {}).get(slug, [])


def _sessao_add_push(request: HttpRequest, slug: str, entrada: dict) -> None:
    todos = request.session.get(_SESSAO_ADD) or {}
    lista = todos.get(slug, [])
    lista.insert(0, entrada)  # mais recente no topo
    todos[slug] = lista[:_SESSAO_ADD_MAX]
    request.session[_SESSAO_ADD] = todos
    request.session.modified = True


def _sessao_add_limpar(request: HttpRequest, slug: str) -> None:
    todos = request.session.get(_SESSAO_ADD) or {}
    if slug in todos:
        del todos[slug]
        request.session[_SESSAO_ADD] = todos
        request.session.modified = True


def _sessao_add_render(request: HttpRequest, projeto) -> list[dict]:
    """Lista da sessão pronta para o template. Reconcilia cada entrada com o estado
    ATUAL do corpus: resolve `item_id` (linha clicável/editável) só quando o item
    ainda existe e não foi removido; marca `removido_corpus` quando o item saiu do
    corpus (ex.: a lista de fontes foi excluída). Cobre entradas antigas sem id."""
    from apps.anco.models import ItemCorpus

    lista = _sessao_add_lista(request, projeto.slug)
    dois = {e.get("doi") for e in lista if e.get("doi")}
    ids = {e.get("item_id") for e in lista if e.get("item_id")}
    ativos_por_doi: dict[str, int] = {}
    if dois:
        ativos_por_doi = dict(
            ItemCorpus.objects.filter(projeto=projeto, removido=False, doi__in=dois).values_list(
                "doi", "pk"
            )
        )
    ativos_ids: set[int] = set()
    if ids:
        ativos_ids = set(
            ItemCorpus.objects.filter(projeto=projeto, removido=False, pk__in=ids).values_list(
                "pk", flat=True
            )
        )
    saida = []
    for e in lista:
        item = dict(e)
        iid = None
        if item.get("doi") and item["doi"] in ativos_por_doi:
            iid = ativos_por_doi[item["doi"]]
        elif item.get("item_id") in ativos_ids:
            iid = item["item_id"]
        item["item_id"] = iid
        # Estava no corpus (novo/repetido) e agora não está mais → removido.
        item["removido_corpus"] = iid is None and item.get("status") in {"novo", "repetido"}
        saida.append(item)
    return saida


def _adicionar_ao_corpus(
    request: HttpRequest, projeto, artigo, *, link_falhou: bool = False
) -> HttpResponse:
    """Inclui o artigo no corpus ANCO do projeto, registra o resultado na lista da
    sessão (progresso visível) e volta ao formulário para adicionar o próximo (PRG)."""
    from apps.anco.importacao import registrar_artigo_no_corpus

    item, criado = registrar_artigo_no_corpus(projeto, artigo, request.user)
    if item is None:
        status = "legado"  # já no acervo curado: isento
    elif criado:
        status = "novo"
    else:
        status = "repetido"  # já estava no corpus
    _sessao_add_push(
        request,
        projeto.slug,
        {
            "titulo": artigo.titulo or "(sem título)",
            "doi": artigo.doi or "",
            "ano": artigo.ano or "",
            "status": status,
            "link_falhou": bool(link_falhou),
            # id do item no corpus → torna a linha clicável/editável na sessão.
            # Legado (item None) fica só-leitura, sem link.
            "item_id": item.pk if item is not None else None,
        },
    )
    return redirect(f"{reverse('cadastrar_artigo')}?projeto={projeto.slug}")


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
    projeto_corpus = _projeto_corpus(request)
    # "Concluir": limpa a lista da sessão e leva ao corpus do projeto.
    if request.method == "GET" and projeto_corpus is not None and request.GET.get("concluir"):
        _sessao_add_limpar(request, projeto_corpus.slug)
        return redirect("anco_corpus", slug=projeto_corpus.slug)
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
            if projeto_corpus is not None:
                return _adicionar_ao_corpus(request, projeto_corpus, existente)
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

        # Inclusão avulsa (Revisão ANCO): cadastra um artigo próprio. Vindo de um
        # projeto ("Artigo individual" no painel), entra no **corpus** do projeto
        # (vira fonte, pode ser sorteado). Sem projeto, inicia a própria análise.
        form = ArtigoMetadadosForm(request.POST)
        if form.is_valid():
            artigo = form.save(commit=False)
            artigo.eh_legado = False
            artigo.save()
            # Valida link e aplica resultado no Artigo. Salvar NÃO deve falhar por
            # causa do link: se a verificação der erro, sinaliza (link_falhou) para
            # a lista da sessão avisar, mas o artigo já está salvo.
            link_falhou = False
            try:
                resultado = validar_link(artigo.link_acesso)
                aplicar_resultado_no_artigo(artigo, resultado)
            except Exception:  # noqa: BLE001
                link_falhou = True
            if projeto_corpus is not None:
                return _adicionar_ao_corpus(
                    request, projeto_corpus, artigo, link_falhou=link_falhou
                )
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
        {
            "form": form,
            "lookup_form": lookup_form,
            "projeto_corpus": projeto_corpus,
            "projeto_slug": request.GET.get("projeto") or request.POST.get("projeto") or "",
            "sessao_add": _sessao_add_render(request, projeto_corpus) if projeto_corpus else [],
            "n_corpus": (
                projeto_corpus.itens.filter(removido=False).count() if projeto_corpus else None
            ),
        },
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
        # Contexto de projeto ("Artigo individual"): habilita o botão
        # "Adicionar ao corpus assim mesmo" quando o artigo já existe.
        "projeto_slug": (request.GET.get("projeto") or "").strip(),
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
    # Gate ANCO: artigo de corpus ANCO só é analisável por quem foi sorteado.
    # Curador (admin/global OU curador do projeto ANCO) analisa em qualquer tempo.
    if not _eh_admin(request.user):
        from apps.anco.models import AtribuicaoANCO, ItemCorpus, MembroANCO

        em_corpus_anco = ItemCorpus.objects.filter(artigo=artigo, removido=False).exists()
        if em_corpus_anco:
            eh_curador_anco = MembroANCO.objects.filter(
                projeto__itens__artigo=artigo,
                projeto__itens__removido=False,
                usuario=request.user,
                papel=MembroANCO.Papel.CURADOR,
            ).exists()
            tem_sorteio = AtribuicaoANCO.objects.filter(
                analista=request.user, artigo=artigo
            ).exists()
            if not (eh_curador_anco or tem_sorteio):
                return HttpResponseForbidden(
                    "Este artigo do corpus ANCO só pode ser analisado por quem foi sorteado. "
                    "Aguarde o sorteio do curador."
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
    ("estrutura", "Estrutura do artigo"),
]

# Termos AnCo destacados (<mark>) na aba Identificação para ajudar o analista a
# ver onde o termo aparece (apoia a decisão de presença/pertinência).
_TERMOS_REALCE_PADRAO = (
    "análise cognitiva, cognitive analysis, cognitive analytics, cognição, cognition"
)


def _termos_realce_do_artigo(artigo) -> str:
    """Termos a destacar no título/resumo. Usa os `termos_realce` do projeto de
    triagem do artigo (se houver) ou o padrão AnCo."""
    try:
        from apps.triagem.models import RegistroTriagem

        reg = (
            RegistroTriagem.objects.filter(artigo=artigo)
            .exclude(protocolo__termos_realce="")
            .select_related("protocolo")
            .first()
        )
        if reg and reg.protocolo.termos_realce.strip():
            return reg.protocolo.termos_realce
    except Exception:  # noqa: BLE001 — triagem é opcional; nunca quebra o editor
        pass
    return _TERMOS_REALCE_PADRAO


def _ficha_sem_area(artigo) -> dict:
    """Ficha do artigo p/ o componente único, sem a 'área' — que no editor é um
    campo EDITÁVEL à parte (evita mostrar duas vezes)."""
    f = artigo.ficha()
    f["area"] = ""
    return f


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

    # Aba inicial (deep-link / stepper da resenha). Não ramifica a renderização:
    # as 3 abas são renderizadas juntas e alternadas no cliente.
    passo_inicial = request.GET.get("passo", "identificacao")
    if passo_inicial not in dict(PASSOS):
        passo_inicial = "identificacao"

    artigo_form = ArtigoAreaForm(request.POST or None, instance=analise.artigo)
    presenca_form = AnalisePresencaForm(request.POST or None, instance=analise)
    estrutura_form = AnaliseEstruturaForm(request.POST or None, instance=analise)

    # Caminho normal = auto-save incremental (autosave_analise_view) + troca de aba
    # no cliente. Este POST é o fallback sem-JS: salva as três abas de uma vez.
    if request.method == "POST" and all(
        f.is_valid() for f in (artigo_form, presenca_form, estrutura_form)
    ):
        artigo_form.save()  # grande área (Artigo)
        presenca_form.save()  # presença/pertinência (mesma instância Analise)
        instance = estrutura_form.save(commit=False)
        if eh_admin and analise.analista_id != user.id:
            _stampar_edicao(instance, user)  # edição administrativa: stamp
        instance.save()
        estrutura_form.save_m2m()  # epistemologia/teoria (M2M)
        messages.success(request, "Análise salva.")
        return redirect(request.path)

    return render(
        request,
        "acervo/editar_analise.html",
        {
            "analise": analise,
            "passos": PASSOS,
            "passo_inicial": passo_inicial,
            "artigo_form": artigo_form,
            "presenca_form": presenca_form,
            "estrutura_form": estrutura_form,
            "resenha": getattr(analise, "resenha", None),
            "eh_admin_edit": eh_admin and analise.analista_id != user.id,
            "campos_faltantes": analise.campos_faltantes_submissao(),
            "termos_realce": _termos_realce_do_artigo(analise.artigo),
            "ficha": _ficha_sem_area(analise.artigo),
            "autosave_url": reverse("autosave_analise", args=[analise.pk]),
            "resenha_url": reverse("editar_resenha", args=[analise.pk]),
        },
    )


@_exige_editor
def editar_metadados_artigo_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Editar os metadados do ARTIGO da análise (título, autores, resumo,
    palavras-chave, link, etc.) — para o analista completar/corrigir campos que
    não vieram na importação. Autor (em janela editável) ou curador/admin.
    Acervo curado (`eh_legado`) é intocável: bloqueado."""
    analise = get_object_or_404(Analise, pk=analise_id)
    user = request.user
    eh_admin = _eh_admin(user)

    if not eh_admin and analise.analista_id != user.id:
        return HttpResponseForbidden("Apenas o analista autor (ou curador/admin) pode editar.")
    if analise.artigo.eh_legado:
        return HttpResponseForbidden(
            "Acervo curado (legado) é somente-leitura — seus dados não são editáveis aqui."
        )
    if not (eh_admin or analise.pode_ser_modificada):
        messages.info(request, "Esta análise não pode mais ser editada nesta janela.")
        return redirect("editar_analise", analise_id=analise.pk)

    artigo = analise.artigo
    if request.method == "POST":
        form = ArtigoMetadadosForm(request.POST, instance=artigo)
        if form.is_valid():
            form.save()
            _espelhar_no_corpus(artigo)  # mantém ItemCorpus (ANCO) em sincronia
            messages.success(request, "Dados do artigo atualizados.")
            return redirect("editar_analise", analise_id=analise.pk)
    else:
        form = ArtigoMetadadosForm(instance=artigo)

    return render(
        request,
        "acervo/editar_metadados_artigo.html",
        {"analise": analise, "artigo": artigo, "form": form},
    )


def _espelhar_no_corpus(artigo) -> None:
    """Reflete os metadados editados do Artigo nos `ItemCorpus` (ANCO) que o
    referenciam, para o corpus/sorteio não ficarem defasados. Best-effort."""
    try:
        from apps.anco.models import ItemCorpus
    except Exception:  # noqa: BLE001 — ANCO é opcional
        return
    ItemCorpus.objects.filter(artigo=artigo, removido=False).update(
        titulo=artigo.titulo,
        autores=artigo.autores or "",
        ano=artigo.ano,
        doi=artigo.doi or "",
        isbn=artigo.isbn or "",
        resumo=artigo.resumo or "",
        palavras_chaves=artigo.palavras_chaves or "",
        titulo_periodico=artigo.titulo_periodico or "",
        idioma=artigo.idioma or "",
        link=artigo.link_acesso or "",
    )


def ver_analise_analista_view(
    request: HttpRequest, artigo_id: int, analista_id: int
) -> HttpResponse:
    """Visualização (curador) da análise de um analista — MESMA tela do editor,
    porém em **modo leitura**. Funciona mesmo se o analista ainda não iniciou:
    monta uma análise em branco **transitória** (não grava nada), para o curador
    ver a grade que o analista vê, sem risco de alterar o trabalho dele."""
    from django.contrib.auth import get_user_model

    if not request.user.is_authenticated:
        return redirect("account_login")
    if not _eh_admin(request.user):
        return HttpResponseForbidden(
            "Apenas curador/admin pode visualizar a análise de outro analista."
        )
    User = get_user_model()
    artigo = get_object_or_404(Artigo, pk=artigo_id)
    analista = get_object_or_404(User, pk=analista_id)
    analise = (
        Analise.objects.select_related("artigo")
        .filter(artigo=artigo, analista=analista)
        .first()
    )
    transitoria = analise is None
    if transitoria:
        analise = Analise(artigo=artigo, analista=analista)  # em memória, não salva

    passo_inicial = request.GET.get("passo", "identificacao")
    if passo_inicial not in dict(PASSOS):
        passo_inicial = "identificacao"

    # Para onde voltar após aprovar/devolver (ex.: a tela de sorteio). Seguro.
    from django.utils.http import url_has_allowed_host_and_scheme

    prox = request.GET.get("next") or ""
    if not (
        prox
        and url_has_allowed_host_and_scheme(
            prox, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    ):
        prox = ""

    return render(
        request,
        "acervo/editar_analise.html",
        {
            "analise": analise,
            "passos": PASSOS,
            "passo_inicial": passo_inicial,
            "artigo_form": ArtigoAreaForm(instance=analise.artigo),
            "presenca_form": AnalisePresencaForm(instance=analise),
            "estrutura_form": AnaliseEstruturaForm(instance=analise),
            "resenha": getattr(analise, "resenha", None) if analise.pk else None,
            "somente_leitura": True,
            "analista_alvo": analista,
            "analise_transitoria": transitoria,
            # Aprovar/devolver aparecem na própria visualização quando "Enviada".
            "pode_aprovar": (not transitoria) and analise.status == Analise.Status.SUBMETIDA,
            "next_url": prox,
            "campos_faltantes": [],
            "termos_realce": _termos_realce_do_artigo(analise.artigo),
            "ficha": _ficha_sem_area(analise.artigo),
            "autosave_url": "",
            "resenha_url": "",
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

    # Auto-save PARCIAL: cada campo posta só o que mudou. Um form com TODOS os
    # campos ligado a um POST parcial sobrescreveria os campos ausentes com vazio
    # (texto → "", M2M → []) — apagando o resto. Por isso limitamos o form aos
    # campos realmente presentes no POST.
    from django.forms import modelform_factory

    # 1) Campos da própria Análise (presença + estrutura).
    campos = [c for c in AnaliseCompletaForm.base_fields if c in request.POST]
    if campos:
        FormParcial = modelform_factory(Analise, form=AnaliseCompletaForm, fields=campos)
        form = FormParcial(request.POST, instance=analise)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        instance = form.save(commit=False)
        if eh_admin and analise.analista_id != user.id:
            _stampar_edicao(instance, user)
        instance.save()
        form.save_m2m()  # persiste só os M2M presentes (epistemologia/teoria)

    # 2) Grande área — campo do Artigo (aba Identificação). Nunca toca o legado.
    if "area" in request.POST and not analise.artigo.eh_legado:
        area_form = ArtigoAreaForm(request.POST, instance=analise.artigo)
        if area_form.is_valid():
            area_form.save()

    # 3) Devolve a lista de campos ainda faltantes p/ a UI atualizar o bloco de
    #    submissão ao vivo, sem recarregar a página.
    return JsonResponse(
        {
            "ok": True,
            "salvo_em": timezone.localtime().strftime("%H:%M:%S"),
            "faltantes": analise.campos_faltantes_submissao(),
        }
    )


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
        # Devolve o analista à sua fila de sorteados ANCO (não à triagem PRISMA).
        projeto = _projeto_anco_do_analista(request.user, analise.artigo)
        if projeto:
            return redirect("anco_analisar", slug=projeto.slug)
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
def autosave_resenha_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Auto-save do texto da resenha. Resposta JSON com timestamp do save.

    Espelha `autosave_analise_view`: evita que o analista perca um texto longo.
    Não salva enquanto a resenha está em revisão cega (não é editável então).
    """
    try:
        resenha = _get_resenha_editavel(request, analise_id)
    except PermissionError:
        return HttpResponseForbidden("Apenas o autor pode salvar a resenha.")

    if resenha.analise.artigo.eh_legado and not _eh_admin(request.user):
        return HttpResponseForbidden("O acervo histórico (legado) não é editável por analistas.")

    if resenha.status == Resenha.Status.EM_REVISAO:
        return JsonResponse(
            {"ok": False, "error": "Resenha em revisão cega — não editável agora."},
            status=400,
        )

    form = ResenhaForm(request.POST, instance=resenha)
    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True, "salvo_em": timezone.localtime().strftime("%H:%M:%S")})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


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


def _destino_curadoria(request: HttpRequest):
    """Para onde voltar após curar: `next` seguro (ex.: tela de sorteio ANCO) ou
    a fila de curadoria. Permite aprovar/devolver de fora da fila."""
    from django.utils.http import url_has_allowed_host_and_scheme

    destino = request.POST.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(destino)
    return redirect("fila_curadoria")


@_exige_curador
@require_POST
def aprovar_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    from .tasks import notificar_publicacao_analise

    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status != Analise.Status.SUBMETIDA:
        messages.info(request, "Esta análise não está na fila de curadoria.")
        return _destino_curadoria(request)
    agora = timezone.now()
    analise.status = Analise.Status.PUBLICADA
    analise.publicada_em = agora
    analise.aprovada_por = request.user
    analise.aprovada_em = agora
    analise.save()
    notificar_publicacao_analise(analise)
    messages.success(request, "Análise aprovada e publicada no acervo.")
    return _destino_curadoria(request)


@_exige_curador
@require_POST
def devolver_analise_view(request: HttpRequest, analise_id: int) -> HttpResponse:
    """Pedir ajustes (-> rascunho) ou rejeitar (-> rejeitada), conforme `acao`."""
    from .tasks import notificar_analise_devolvida

    analise = get_object_or_404(Analise, pk=analise_id)
    if analise.status != Analise.Status.SUBMETIDA:
        messages.info(request, "Esta análise não está na fila de curadoria.")
        return _destino_curadoria(request)
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
    return _destino_curadoria(request)


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
