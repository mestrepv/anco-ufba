"""Views do app core: home, solicitacao de promocao, status, ferramenta DOI."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.acervo.services import lookup_doi

from .forms import SolicitacaoCadastroForm
from .models import SolicitacaoCadastro


def consultar_doi_view(request: HttpRequest) -> HttpResponse:
    """
    Ferramenta de inspeção de DOI. Reusa o serviço lookup_doi de
    apps.acervo.services (Crossref + cache 24h).
    """
    doi_raw = request.GET.get("doi", "").strip()
    dados = None
    if doi_raw:
        resultado = lookup_doi(doi_raw)
        if resultado.encontrado:
            dados = dict(resultado.dados)
            # O template antigo espera autores como [{nome, afiliacao}]; adapta.
            dados["autores"] = [
                {"nome": nome, "afiliacao": ""} for nome in dados.get("autores", [])
            ]
        else:
            dados = {"erro": resultado.erro or "DOI não encontrado", "doi": doi_raw}
    return render(request, "ferramentas/consultar_doi.html", {"dados": dados, "doi_raw": doi_raw})


def home_view(request: HttpRequest) -> HttpResponse:
    """Pagina inicial publica. Aponta para login institucional ou para o acervo."""
    return render(request, "core/home.html")


def teste_design_view(request: HttpRequest) -> HttpResponse:
    """Página de teste do design system — remover antes de ir para produção."""
    colors = [
        ("paper", "#FBF9F4"), ("paper-2", "#F5F1E8"), ("paper-3", "#EDE7DA"),
        ("rule", "#E5DFCF"), ("rule-strong", "#D4CCB8"),
        ("ink", "#1A1816"), ("ink-2", "#3A352E"), ("ink-3", "#6B655B"), ("ink-4", "#948D80"),
        ("gold", "#B8862C"), ("gold-deep", "#8C6520"),
        ("review-bg", "#FBF7E8"), ("review-rule", "#E8DCA8"),
        ("danger", "#A03A2A"), ("ok", "#4A6B3A"), ("info", "#3A5A7A"),
    ]
    return render(request, "_teste_design.html", {"colors": colors})


@login_required
def solicitar_promocao_view(request: HttpRequest) -> HttpResponse:
    """
    Formulario de solicitacao de promocao a analista.

    Se ja existe solicitacao do usuario, redireciona para a tela de status.
    Se o usuario ja eh analista ou curador, redireciona para a home.
    """
    user = request.user
    if user.eh_analista:
        messages.info(request, "Você já é analista — não precisa solicitar promoção.")
        return redirect("home")

    existente = SolicitacaoCadastro.objects.filter(usuario=user).first()
    if existente:
        return redirect("promocao_status")

    if request.method == "POST":
        form = SolicitacaoCadastroForm(request.POST, usuario=user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Solicitação enviada. Você receberá um e-mail quando for analisada.",
            )
            return redirect("promocao_status")
    else:
        form = SolicitacaoCadastroForm(usuario=user)

    return render(request, "core/solicitar_promocao.html", {"form": form})


@login_required
def promocao_status_view(request: HttpRequest) -> HttpResponse:
    """Mostra o status da solicitacao do usuario logado."""
    solicitacao = SolicitacaoCadastro.objects.filter(usuario=request.user).first()
    return render(
        request,
        "core/promocao_status.html",
        {"solicitacao": solicitacao},
    )
