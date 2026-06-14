"""Views do módulo Revisão ANCO — montadas em /anco/ (gated por ANCO_ATIVO).

Fluxo (sem triagem): Adicionar fontes → Corpus → Sortear → Analisar (Matriz AnCo,
via apps/acervo). Escopo por projeto (`/anco/p/<slug>/…`).
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import estatisticas as stats
from . import sorteio as sorteio_mod
from .forms import ImportarFonteForm
from .importacao import importar_para_fonte
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
        projeto = get_object_or_404(ProjetoANCO, slug=slug)
        if not projeto.eh_membro(request.user) and not request.user.is_staff:
            return HttpResponseForbidden("Você não é membro deste projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


def _projeto_curador(view):
    @wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
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
        "fontes": projeto.fontes.select_related("base_consulta", "criado_por").all(),
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
    itens = projeto.itens.filter(removido=False).select_related("artigo")
    if q:
        itens = itens.filter(titulo__icontains=q)
    itens = itens.order_by("-criado_em")
    atribuidos = set(
        AtribuicaoANCO.objects.filter(
            analista=request.user, sorteio__projeto=projeto
        ).values_list("artigo_id", flat=True)
    )
    contexto = {
        "projeto": projeto,
        "eh_curador": projeto.eh_curador_no(request.user),
        "itens": itens,
        "total": projeto.itens.filter(removido=False).count(),
        "q": q,
        "atribuidos": atribuidos,
    }
    return render(request, "anco/corpus.html", contexto)


@_projeto_curador
@require_POST
def corpus_excluir_view(request: HttpRequest, projeto: ProjetoANCO) -> HttpResponse:
    from django.utils import timezone

    item = get_object_or_404(ItemCorpus, pk=request.POST.get("item_id"), projeto=projeto)
    item.removido = True
    item.removido_por = request.user
    item.removido_em = timezone.now()
    item.motivo_remocao = (request.POST.get("motivo") or "")[:300]
    item.save(update_fields=["removido", "removido_por", "removido_em", "motivo_remocao"])
    messages.info(request, "Item removido do corpus.")
    return redirect("anco_corpus", slug=projeto.slug)


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
        res = sorteio_mod.executar_sorteio(
            projeto, modo_revisao=modo, cota=cota, por=request.user
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
    contexto = {
        "projeto": projeto,
        "sorteios": sorteios,
        "n_corpus": projeto.itens.filter(removido=False, artigo__isnull=False).count(),
        "n_analistas": projeto.membros.filter(papel=MembroANCO.Papel.ANALISTA).count(),
        "modos": SorteioANCO.ModoRevisao.choices,
    }
    return render(request, "anco/sorteio.html", contexto)


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
