"""Views do app core: home, solicitacao de promocao, status."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import SolicitacaoCadastroForm
from .models import SolicitacaoCadastro


def home_view(request: HttpRequest) -> HttpResponse:
    """Pagina inicial publica. Aponta para login institucional ou para o acervo."""
    return render(request, "core/home.html")


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
