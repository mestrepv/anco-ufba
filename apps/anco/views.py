"""Views do módulo Revisão ANCO — montadas em /anco/ (gated por ANCO_ATIVO).

Fluxo (sem triagem): Adicionar fontes → Corpus → Sortear → Analisar (Matriz AnCo,
via apps/acervo). Escopo por projeto (`/anco/p/<slug>/…`).
"""

from __future__ import annotations

from collections import Counter
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import estatisticas as stats
from . import sorteio as sorteio_mod
from .forms import ImportarFonteForm, ItemCorpusForm
from .importacao import importar_para_fonte, sincronizar_artigo
from .models import AtribuicaoANCO, FonteImport, ItemCorpus, MembroANCO, ProjetoANCO, SorteioANCO
from .parsers import analisar_arquivo, decodificar, parse_conteudo

User = get_user_model()


# --------------------------------------------------------------------------- #
# Decorators de escopo por projeto
# --------------------------------------------------------------------------- #


def _projeto_membro(view):
    @wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        if not request.user.acessa_anco():
            return HttpResponseForbidden("Módulo Revisão ANCO indisponível para você.")
        projeto = get_object_or_404(ProjetoANCO, slug=slug)
        if not projeto.eh_membro(request.user) and not request.user.is_staff:
            return HttpResponseForbidden("Você não é membro deste projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


def _projeto_curador(view):
    @wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        if not request.user.acessa_anco():
            return HttpResponseForbidden("Módulo Revisão ANCO indisponível para você.")
        projeto = get_object_or_404(ProjetoANCO, slug=slug)
        if not projeto.eh_curador_no(request.user):
            return HttpResponseForbidden("Apenas o curador do projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------- #
# Lista de projetos + painel
# --------------------------------------------------------------------------- #


@login_required
def projetos_view(request: HttpRequest) -> HttpResponse:
    if not request.user.acessa_anco():
        return HttpResponseForbidden("Módulo Revisão ANCO indisponível para você.")
    meus = ProjetoANCO.objects.filter(membros__usuario=request.user).distinct().order_by("nome")
    return render(request, "anco/projetos.html", {"projetos": meus})


@_projeto_membro
def painel_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    eh_curador = projeto.eh_curador_no(request.user)
    itens = projeto.itens.filter(removido=False)
    atribuidos = AtribuicaoANCO.objects.filter(
        analista=request.user, sorteio__projeto=projeto
    ).values_list("artigo_id", flat=True)
    contexto = {
        "projeto": projeto,
        "eh_curador": eh_curador,
        "n_corpus": itens.count(),
        "n_fontes": projeto.fontes.count(),
        "fontes": (
            projeto.fontes.select_related("base_consulta", "criado_por")
            # n_itens = itens ainda no corpus (não removidos): reflete remoções.
            .annotate(n_itens=Count("itens", filter=Q(itens__removido=False)))
            .order_by(F("importado_em").desc(nulls_last=True), "-criado_em")
        ),
        "membros": projeto.membros.select_related("usuario").order_by("-papel"),
        "n_membros": projeto.membros.count(),
        "minha_a_analisar": len(set(atribuidos)),
        "tem_sorteio": projeto.sorteios.exists(),
    }
    return render(request, "anco/painel.html", contexto)


# --------------------------------------------------------------------------- #
# Importação → corpus
# --------------------------------------------------------------------------- #


@_projeto_membro
def importar_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    if request.method == "POST":
        form = ImportarFonteForm(request.POST, request.FILES)
        if form.is_valid():
            enviado = form.cleaned_data["arquivo"]
            raw = enviado.read()
            enviado.seek(0)
            info = analisar_arquivo(enviado.name, raw)
            if not info["ok"]:
                form.add_error("arquivo", f"{info['erro']} {info.get('dica', '')}".strip())
            else:
                cd = form.cleaned_data
                fonte = FonteImport.objects.create(
                    projeto=projeto,
                    base_consulta=cd["base_consulta"],
                    outra_base=cd["outra_base"],
                    string_busca=cd["string_busca"],
                    data_busca=cd["data_busca"],
                    formato=cd["formato"] or info["formato"],
                    arquivo=enviado,
                    criado_por=request.user,
                )
                registros = parse_conteudo(decodificar(raw), fonte.formato)
                res = importar_para_fonte(fonte, registros)
                messages.success(
                    request,
                    f"Importados {res.novos} novo(s) item(ns) ao corpus "
                    f"({res.duplicados} repetido(s), {res.ignorados} ignorado(s)).",
                )
                return redirect("anco_corpus", slug=projeto.slug)
    else:
        form = ImportarFonteForm()
    return render(request, "anco/importar.html", {"projeto": projeto, "form": form})


def _pode_excluir_fonte(projeto: ProjetoANCO, fonte: FonteImport, user) -> bool:
    """Quem exclui uma lista importada: quem a importou (`criado_por`) ou curador/admin."""
    return projeto.eh_curador_no(user) or fonte.criado_por_id == user.id


@_projeto_membro
def fonte_excluir_view(request: HttpRequest, projeto: ProjetoANCO, fonte_id: int) -> HttpResponse:
    """Exclui uma lista (FonteImport) com tela de confirmação — quem importou ou
    um curador. Itens novos sem análise e só desta fonte saem do corpus;
    conteúdo no acervo é mantido."""
    from .importacao import excluir_fonte, resumo_exclusao_fonte

    fonte = get_object_or_404(FonteImport, pk=fonte_id, projeto=projeto)
    if not _pode_excluir_fonte(projeto, fonte, request.user):
        return HttpResponseForbidden("Só quem importou a lista (ou um curador) pode excluí-la.")
    if request.method == "POST":
        nome = fonte.base_nome or "(sem base)"
        removidos = excluir_fonte(fonte, request.user)
        messages.success(
            request,
            f"Lista “{nome}” excluída. {removidos} item(ns) novo(s) removido(s) do corpus; "
            "conteúdo no acervo/analisado foi mantido.",
        )
        return redirect("anco_painel", slug=projeto.slug)
    total, mantidos, removidos = resumo_exclusao_fonte(fonte)
    return render(
        request,
        "anco/fonte_excluir.html",
        {
            "projeto": projeto,
            "fonte": fonte,
            "total": total,
            "mantidos": mantidos,
            "removidos": removidos,
        },
    )


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


@_projeto_membro
def corpus_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    filtro = request.GET.get("filtro") or ""
    fonte_sel = (request.GET.get("fonte") or "").strip()
    itens = projeto.itens.filter(removido=False).select_related("artigo")
    if q:
        itens = itens.filter(titulo__icontains=q)
    if filtro == "acervo":
        itens = itens.filter(artigo__eh_legado=True)
    elif filtro == "novos":
        itens = itens.filter(artigo__eh_legado=False)
    # `fonte` no filtro passou a ser o NOME da base (agrupa importações da mesma
    # base, independente de data/quem importou), não mais um id de importação.
    if fonte_sel:
        itens = itens.filter(
            Q(origem_fontes__base_consulta__nome=fonte_sel)
            | Q(origem_fontes__base_consulta__isnull=True, origem_fontes__outra_base=fonte_sel)
        )
    # `import` = uma importação específica (fonte por pk), vindo dos links do painel:
    # mostra só os itens daquela importação.
    import_sel = (request.GET.get("import") or "").strip()
    import_fonte = None
    if import_sel.isdigit():
        import_fonte = (
            projeto.fontes.select_related("base_consulta", "criado_por")
            .filter(pk=int(import_sel))
            .first()
        )
        if import_fonte is not None:
            itens = itens.filter(origem_fontes__pk=import_fonte.pk)
    itens = list(
        itens.order_by("-criado_em").distinct().prefetch_related("origem_fontes__criado_por")
    )
    # Nome(s) de quem importou cada item (distintos, das fontes de origem).
    for it in itens:
        nomes = []
        for f in it.origem_fontes.all():
            if f.criado_por_id:
                nome = f.criado_por.nome_exibicao or f.criado_por.email
                if nome and nome not in nomes:
                    nomes.append(nome)
        it.importado_por = ", ".join(nomes)
    atribuidos = set(
        AtribuicaoANCO.objects.filter(
            analista=request.user, sorteio__projeto=projeto
        ).values_list("artigo_id", flat=True)
    )
    base = projeto.itens.filter(removido=False)
    # "No acervo" = artigo já curado (eh_legado): pré-validado, fora do sorteio.
    n_acervo = base.filter(artigo__eh_legado=True).count()
    total = base.count()
    # Quem pode editar/remover cada item: curador/admin (todos) ou o importador.
    pode_gerir_todos = projeto.eh_curador_no(request.user) or request.user.is_staff
    geridos = (
        set()
        if pode_gerir_todos
        else set(
            base.filter(origem_fontes__criado_por=request.user).values_list("pk", flat=True)
        )
    )
    # Filtro de procedência agrupado POR BASE (não por importação/data). Várias
    # importações da mesma base viram uma opção só, com o total de itens distintos.
    grupos: dict[str, list[int]] = {}
    for f in projeto.fontes.select_related("base_consulta"):
        grupos.setdefault(f.base_nome or "(sem base)", []).append(f.pk)
    bases = []
    for nome, pks in grupos.items():
        n = projeto.itens.filter(removido=False, origem_fontes__in=pks).distinct().count()
        if n:
            bases.append({"nome": nome, "n": n})
    bases.sort(key=lambda b: (-b["n"], b["nome"]))
    contexto = {
        "projeto": projeto,
        "eh_curador": projeto.eh_curador_no(request.user),
        "itens": itens,
        "total": total,
        "n_acervo": n_acervo,
        "n_novos": total - n_acervo,
        "q": q,
        "filtro": filtro,
        "bases": bases,
        "fonte_sel": fonte_sel,
        "import_sel": import_sel,
        "import_fonte": import_fonte,
        "atribuidos": atribuidos,
        "pode_gerir_todos": pode_gerir_todos,
        "geridos": geridos,
    }
    return render(request, "anco/corpus.html", contexto)


def _no_acervo(item: ItemCorpus) -> bool:
    """Item cujo artigo já está no acervo: legado curado ou com análise publicada.
    Uma vez no acervo, só curador edita/remove."""
    from apps.acervo.models import Analise

    art = item.artigo
    if not art:
        return False
    if art.eh_legado:
        return True
    return Analise.objects.filter(
        artigo=art, status__in=[Analise.Status.PUBLICADA, Analise.Status.LEGADO]
    ).exists()


def _pode_gerenciar_item(projeto: ProjetoANCO, item: ItemCorpus, user) -> bool:
    """Quem edita/remove um item do corpus: curador/admin sempre; quem o adicionou
    desde que o item ainda **não esteja no acervo** (acervo é só do curador)."""
    if projeto.eh_curador_no(user) or user.is_staff:
        return True
    if _no_acervo(item):
        return False
    return item.origem_fontes.filter(criado_por=user).exists()


@_projeto_membro
@require_POST
def corpus_excluir_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    from django.utils import timezone

    item = get_object_or_404(ItemCorpus, pk=request.POST.get("item_id"), projeto=projeto)
    if not _pode_gerenciar_item(projeto, item, request.user):
        return HttpResponseForbidden(
            "Sem permissão: itens no acervo são geridos só pelo curador."
        )
    item.removido = True
    item.removido_por = request.user
    item.removido_em = timezone.now()
    item.motivo_remocao = (request.POST.get("motivo") or "")[:300]
    item.save(update_fields=["removido", "removido_por", "removido_em", "motivo_remocao"])
    messages.info(request, "Item removido do corpus.")
    # Volta para a tela de origem quando informada e segura (ex.: o painel de
    # "Artigo individual"), preservando o loop de adição.
    destino = request.POST.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(destino)
    return redirect("anco_corpus", slug=projeto.slug)


@_projeto_membro
def corpus_editar_view(request: HttpRequest, projeto: ProjetoANCO, item_id: int) -> HttpResponse:
    """Página de um item do corpus: ficha + link para o artigo + navegação
    avançar/voltar entre os itens. Editável (sincroniza no `Artigo`) por quem o
    adicionou ou curador/admin; item já no acervo curado (`eh_legado`) é só-leitura."""
    from django.urls import reverse

    from apps.publico.services import doi_to_slug

    item = get_object_or_404(ItemCorpus, pk=item_id, projeto=projeto, removido=False)
    eh_legado = bool(item.artigo and item.artigo.eh_legado)
    pode_editar = _pode_gerenciar_item(projeto, item, request.user) and not eh_legado

    if request.method == "POST":
        if not pode_editar:
            return HttpResponseForbidden(
                "Item só-leitura: você não pode editá-lo (acervo curado ou sem permissão)."
            )
        form = ItemCorpusForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            sincronizar_artigo(item)
            messages.success(request, "Item atualizado.")
            return redirect("anco_corpus_editar", slug=projeto.slug, item_id=item.pk)
    else:
        form = ItemCorpusForm(instance=item) if pode_editar else None

    # Navegação avançar/voltar. Por padrão percorre todo o corpus (ordem da
    # listagem); vindo do sorteio (`ctx=elegiveis`), percorre **só os elegíveis**
    # com os filtros ativos, preservando o contexto nos links.
    ctx_eleg = request.GET.get("ctx") == "elegiveis"
    nav_qs = ""
    ids = None
    if ctx_eleg:
        com_resumo, tipos_sel = _ler_filtros(request.GET)
        eleg_ids = [
            it.pk
            for it in sorteio_mod.itens_elegiveis(
                projeto, tipos=tipos_sel, exigir_resumo=com_resumo
            )
        ]
        if item.pk in eleg_ids:  # item ainda elegível com esses filtros
            ids = eleg_ids
            qs = ["ctx=elegiveis", "filtros=1"]
            if com_resumo:
                qs.append("com_resumo=1")
            qs += [f"tipos={t}" for t in tipos_sel]
            nav_qs = "&".join(qs)
    if ids is None:  # sem contexto de elegíveis (ou item saiu do conjunto)
        ctx_eleg = False
        ids = list(projeto.itens.filter(removido=False).values_list("pk", flat=True))

    i = ids.index(item.pk)
    suf = f"?{nav_qs}" if nav_qs else ""
    url_anterior = (
        reverse("anco_corpus_editar", args=[projeto.slug, ids[i - 1]]) + suf if i > 0 else ""
    )
    url_proximo = (
        reverse("anco_corpus_editar", args=[projeto.slug, ids[i + 1]]) + suf
        if i < len(ids) - 1
        else ""
    )
    doi_slug = doi_to_slug(item.artigo.doi) if item.artigo and item.artigo.doi else ""
    return render(
        request,
        "anco/corpus_editar.html",
        {
            "projeto": projeto,
            "item": item,
            "form": form,
            "pode_editar": pode_editar,
            "eh_legado": eh_legado,
            "doi_slug": doi_slug,
            "url_anterior": url_anterior,
            "url_proximo": url_proximo,
            "pos": i + 1,
            "total": len(ids),
            "rotulo_nav": "Elegível" if ctx_eleg else "Item",
            "voltar_url": (
                reverse("anco_sorteio", args=[projeto.slug])
                if ctx_eleg
                else reverse("anco_corpus", args=[projeto.slug])
            ),
            # Destaca o termo AnCo (PT/EN) na ficha em leitura.
            "realce_termos": "análise cognitiva, cognitive analysis, cognitive analytics,"
            " cognição, cognition",
        },
    )


# --------------------------------------------------------------------------- #
# Sorteio da análise
# --------------------------------------------------------------------------- #


@_projeto_curador
def sorteio_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    if request.method == "POST":
        if request.POST.get("acao") == "desfazer":
            s = get_object_or_404(SorteioANCO, pk=request.POST.get("sorteio_id"), projeto=projeto)
            n = sorteio_mod.desfazer_sorteio(s)
            messages.success(request, f"Sorteio desfeito ({n} atribuição(ões) removida(s)).")
            return redirect("anco_sorteio", slug=projeto.slug)
        modo = request.POST.get("modo_revisao", SorteioANCO.ModoRevisao.UNICA)
        if modo not in dict(SorteioANCO.ModoRevisao.choices):
            modo = SorteioANCO.ModoRevisao.UNICA
        try:
            cota = max(1, int(request.POST.get("cota", 5)))
        except (TypeError, ValueError):
            cota = 5
        com_resumo, tipos_sel = _ler_filtros(request.POST)
        res = sorteio_mod.executar_sorteio(
            projeto,
            modo_revisao=modo,
            cota=cota,
            por=request.user,
            tipos=tipos_sel,
            exigir_resumo=com_resumo,
        )
        if res.sorteio:
            messages.success(
                request,
                f"Sorteio feito: {res.atribuidas} atribuição(ões) para {res.analistas} analista(s).",
            )
        else:
            messages.info(request, res.motivo or "Nada a sortear.")
        return redirect("anco_sorteio", slug=projeto.slug)

    sorteios = projeto.sorteios.select_related("criado_por").prefetch_related("atribuicoes")
    base = projeto.itens.filter(removido=False, artigo__isnull=False)
    n_acervo = base.filter(artigo__eh_legado=True).values("artigo").distinct().count()
    contexto = {
        "projeto": projeto,
        "sorteios": sorteios,
        "n_acervo": n_acervo,
        "modos": SorteioANCO.ModoRevisao.choices,
        **_contexto_elegiveis(projeto, request),
    }
    return render(request, "anco/sorteio.html", contexto)


def _ler_filtros(params) -> tuple[bool, list[str]]:
    """Lê os filtros do formulário (GET ou POST). Um marcador `filtros` distingue
    "primeira carga" (defaults) de "usuário mexeu": sem o marcador, vale o padrão
    — só resumo ligado, todos os tipos marcados; com o marcador, valem os
    checkboxes literais (desmarcar tudo = nenhum tipo)."""
    todas = [c for c, _ in sorteio_mod.CATEGORIAS_TIPO]
    if "filtros" not in params:
        return True, todas  # padrão: exige resumo, todos os tipos
    com_resumo = "com_resumo" in params
    tipos = [t for t in params.getlist("tipos") if t in todas]
    return com_resumo, tipos


def _contexto_elegiveis(projeto: ProjetoANCO, request: HttpRequest) -> dict:
    """Calcula o pool elegível + contadores p/ os filtros atuais (GET).
    Usado tanto na página cheia quanto no parcial HTMX `_sorteio_elegiveis`."""
    com_resumo, tipos_sel = _ler_filtros(request.GET)
    try:
        cota = max(1, int(request.GET.get("cota", 5)))
    except (TypeError, ValueError):
        cota = 5
    modo = request.GET.get("modo_revisao") or SorteioANCO.ModoRevisao.UNICA

    novos = projeto.itens.filter(removido=False, artigo__isnull=False, artigo__eh_legado=False)
    novos_ids = set(novos.values_list("artigo_id", flat=True))
    ja_atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list("artigo_id", flat=True)
    )
    # Pool que passa no filtro de resumo (todos os tipos) — base para contar por
    # categoria e para aplicar o filtro de tipo (literal) por cima.
    base = sorteio_mod.itens_elegiveis(
        projeto, tipos=None, exigir_resumo=com_resumo, ja_atribuidos=ja_atribuidos
    )
    sel = set(tipos_sel)
    elegiveis = [it for it in base if it.categoria in sel]
    n_eleg = len(elegiveis)

    # Contagem por categoria (dentro do pool que passou no filtro de resumo).
    cont_cat = Counter(it.categoria for it in base)
    tipos_choices = [
        {"val": val, "rotulo": rotulo, "n": cont_cat.get(val, 0), "sel": val in sel}
        for val, rotulo in sorteio_mod.CATEGORIAS_TIPO
    ]

    # Total de novos disponíveis (não atribuídos, qualquer tipo, sem exigir resumo).
    n_disponivel = len(
        sorteio_mod.itens_elegiveis(
            projeto, tipos=None, exigir_resumo=False, ja_atribuidos=ja_atribuidos
        )
    )
    n_ja = len(novos_ids & ja_atribuidos)
    n_sem_resumo = (n_disponivel - len(base)) if com_resumo else 0
    n_analistas = projeto.membros.filter(papel=MembroANCO.Papel.ANALISTA).count()
    assentos = 2 if modo == SorteioANCO.ModoRevisao.DUPLA else 1

    # Paginação do painel de elegíveis (navegação entre as páginas via HTMX).
    paginador = Paginator(elegiveis, 50)
    try:
        num_pagina = int(request.GET.get("pagina", 1))
    except (TypeError, ValueError):
        num_pagina = 1
    pagina_obj = paginador.get_page(num_pagina)
    # Querystring dos filtros ativos, p/ os links de paginação preservarem o estado.
    qs = ["filtros=1", f"cota={cota}", f"modo_revisao={modo}"]
    if com_resumo:
        qs.append("com_resumo=1")
    qs += [f"tipos={t}" for t in tipos_sel]
    return {
        "projeto": projeto,
        "pagina_obj": pagina_obj,
        "qs_filtros": "&".join(qs),
        "n_elegiveis": n_eleg,
        "n_novos": len(novos_ids),
        "n_disponivel": n_disponivel,
        "n_ja_atribuidos": n_ja,
        "n_sem_resumo": n_sem_resumo,
        "n_analistas": n_analistas,
        "cota": cota,
        "vagas_demanda": n_analistas * cota,
        "capacidade": n_eleg * assentos,
        "insuficiente": n_analistas > 0 and n_eleg * assentos < n_analistas * cota,
        "com_resumo": com_resumo,
        "tipos_choices": tipos_choices,
    }


@_projeto_curador
def sorteio_elegiveis_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    """Parcial HTMX: painel de artigos elegíveis + contadores p/ os filtros atuais."""
    return render(request, "anco/_sorteio_elegiveis.html", _contexto_elegiveis(projeto, request))


# --------------------------------------------------------------------------- #
# Estatísticas + Equipe
# --------------------------------------------------------------------------- #


@_projeto_membro
def estatisticas_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    return render(
        request,
        "anco/estatisticas.html",
        {"projeto": projeto, "resumo": stats.resumo(projeto)},
    )


@_projeto_curador
def equipe_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "remover":
            MembroANCO.objects.filter(projeto=projeto, pk=request.POST.get("membro_id")).delete()
            messages.info(request, "Membro removido.")
        elif acao == "mudar_papel":
            m = (
                MembroANCO.objects.filter(projeto=projeto, pk=request.POST.get("membro_id"))
                .select_related("usuario")
                .first()
            )
            novo = request.POST.get("papel")
            if m is None or novo not in dict(MembroANCO.Papel.choices):
                messages.error(request, "Papel inválido.")
            elif m.usuario_id == request.user.id and novo != MembroANCO.Papel.CURADOR:
                messages.error(request, "Você não pode rebaixar a si mesmo.")
            else:
                m.papel = novo
                m.save(update_fields=["papel"])
                messages.success(
                    request, f"{m.usuario.nome_exibicao or m.usuario.email} agora é {m.get_papel_display()}."
                )
        elif acao == "adicionar":
            email = (request.POST.get("email") or "").strip().lower()
            papel = request.POST.get("papel", MembroANCO.Papel.ANALISTA)
            if papel not in dict(MembroANCO.Papel.choices):
                papel = MembroANCO.Papel.ANALISTA
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                messages.error(request, f"Nenhum usuário com e-mail {email!r}.")
            else:
                MembroANCO.objects.get_or_create(
                    projeto=projeto, usuario=user, defaults={"papel": papel}
                )
                messages.success(request, f"{user.email} adicionado(a) como {papel}.")
        return redirect("anco_equipe", slug=projeto.slug)

    membros = projeto.membros.select_related("usuario").order_by("-papel", "usuario__email")
    return render(
        request,
        "anco/equipe.html",
        {"projeto": projeto, "membros": membros, "papeis": MembroANCO.Papel.choices},
    )
