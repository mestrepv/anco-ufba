"""Views do módulo Revisão ANCO — montadas em /anco/ (gated por ANCO_ATIVO).

Fluxo (sem triagem): Adicionar fontes → Corpus → Sortear → Analisar (Matriz AnCo,
via apps/acervo). Escopo por projeto (`/anco/p/<slug>/…`).
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
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
    if fonte_sel.isdigit():
        itens = itens.filter(origem_fontes__pk=int(fonte_sel))
    itens = itens.order_by("-criado_em").distinct()
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
    # Fontes do projeto p/ o filtro de procedência (lista x "Artigos individuais").
    # n_itens = itens não removidos vindos da fonte (casa com o que o filtro mostra).
    fontes = (
        projeto.fontes.select_related("base_consulta")
        .annotate(n_itens=Count("itens", filter=Q(itens__removido=False)))
        .order_by(F("importado_em").desc(nulls_last=True), "-criado_em")
    )
    contexto = {
        "projeto": projeto,
        "eh_curador": projeto.eh_curador_no(request.user),
        "itens": itens,
        "total": total,
        "n_acervo": n_acervo,
        "n_novos": total - n_acervo,
        "q": q,
        "filtro": filtro,
        "fontes": fontes,
        "fonte_sel": fonte_sel,
        "atribuidos": atribuidos,
        "pode_gerir_todos": pode_gerir_todos,
        "geridos": geridos,
    }
    return render(request, "anco/corpus.html", contexto)


def _pode_gerenciar_item(projeto: ProjetoANCO, item: ItemCorpus, user) -> bool:
    """Quem edita/remove um item do corpus: quem o adicionou (importador de
    alguma das fontes do item) ou curador/admin."""
    if projeto.eh_curador_no(user) or user.is_staff:
        return True
    return item.origem_fontes.filter(criado_por=user).exists()


@_projeto_membro
@require_POST
def corpus_excluir_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    from django.utils import timezone

    item = get_object_or_404(ItemCorpus, pk=request.POST.get("item_id"), projeto=projeto)
    if not _pode_gerenciar_item(projeto, item, request.user):
        return HttpResponseForbidden("Só quem adicionou (ou curador/admin) remove este item.")
    item.removido = True
    item.removido_por = request.user
    item.removido_em = timezone.now()
    item.motivo_remocao = (request.POST.get("motivo") or "")[:300]
    item.save(update_fields=["removido", "removido_por", "removido_em", "motivo_remocao"])
    messages.info(request, "Item removido do corpus.")
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

    # Navegação avançar/voltar na ordem do corpus (mesma da listagem).
    ids = list(projeto.itens.filter(removido=False).values_list("pk", flat=True))
    i = ids.index(item.pk)
    url_anterior = (
        reverse("anco_corpus_editar", args=[projeto.slug, ids[i - 1]]) if i > 0 else ""
    )
    url_proximo = (
        reverse("anco_corpus_editar", args=[projeto.slug, ids[i + 1]]) if i < len(ids) - 1 else ""
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
            "voltar_url": reverse("anco_corpus", args=[projeto.slug]),
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
        termo = (request.POST.get("termo") or "").strip()
        campos = request.POST.getlist("campos")
        res = sorteio_mod.executar_sorteio(
            projeto,
            modo_revisao=modo,
            cota=cota,
            por=request.user,
            termo=termo,
            campos=campos,
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
        "campos_choices": sorteio_mod.CAMPOS_CHOICES,
        **_contexto_elegiveis(projeto, request),
    }
    return render(request, "anco/sorteio.html", contexto)


def _contexto_elegiveis(projeto: ProjetoANCO, request: HttpRequest) -> dict:
    """Calcula o pool elegível + contadores p/ os filtros atuais (GET).
    Usado tanto na página cheia quanto no parcial HTMX `_sorteio_elegiveis`."""
    termo = (request.GET.get("termo") or "").strip()
    campos = request.GET.getlist("campos")
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
    elegiveis = sorteio_mod.itens_elegiveis(
        projeto, termo=termo, campos=campos, ja_atribuidos=ja_atribuidos
    )
    n_eleg = len(elegiveis)
    n_ja = len(novos_ids & ja_atribuidos)
    n_fora_filtro = (len(novos_ids) - n_ja) - n_eleg
    n_analistas = projeto.membros.filter(papel=MembroANCO.Papel.ANALISTA).count()
    assentos = 2 if modo == SorteioANCO.ModoRevisao.DUPLA else 1
    return {
        "elegiveis": elegiveis[:100],
        "n_elegiveis": n_eleg,
        "n_mostrando": min(n_eleg, 100),
        "n_novos": len(novos_ids),
        "n_ja_atribuidos": n_ja,
        "n_fora_filtro": n_fora_filtro,
        "n_analistas": n_analistas,
        "cota": cota,
        "vagas_demanda": n_analistas * cota,
        "capacidade": n_eleg * assentos,
        "insuficiente": n_analistas > 0 and n_eleg * assentos < n_analistas * cota,
        "termo": termo,
        "campos_sel": campos,
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
