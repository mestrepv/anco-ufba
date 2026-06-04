"""Views do app core: home, solicitacao de promocao, status, ferramenta DOI."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.acervo.services import lookup_doi

from .forms import PerfilForm


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


# NOTE: as views `solicitar_promocao_view` e `promocao_status_view` foram
# removidas. Agora as solicitações são criadas direto no /perfil/ e o status
# aparece no /painel/.


@login_required
def perfil_view(request: HttpRequest) -> HttpResponse:
    """Edição do perfil do usuário. `?onboarding=1` ativa o tom de boas-vindas."""
    onboarding = request.GET.get("onboarding") == "1"
    if request.method == "POST":
        form = PerfilForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado.")
            # Onboarding concluído → deixa o roteador pós-login decidir o destino
            # (analista vai p/ painel; leitor vai p/ solicitar promoção).
            if onboarding and request.user.perfil_completo_minimo:
                return redirect("pos_login")
            return redirect("perfil")
    else:
        form = PerfilForm(instance=request.user)

    # Estado das solicitações para o JS do botão decidir o label dinamicamente.
    from .models import SolicitacaoCadastro

    user = request.user
    ativas = {
        s.tipo: True
        for s in user.solicitacoes.filter(
            status__in=[
                SolicitacaoCadastro.Status.PENDENTE,
                SolicitacaoCadastro.Status.APROVADA,
            ]
        )
    }
    return render(
        request,
        "core/perfil.html",
        {
            "form": form,
            "onboarding": onboarding,
            "ja_e_analista": user.eh_analista,
            "ja_e_revisor_aprovado": user.revisor_aprovado,
            "tem_sol_analista_ativa": SolicitacaoCadastro.Tipo.ANALISTA in ativas,
            "tem_sol_revisor_ativa": SolicitacaoCadastro.Tipo.REVISOR in ativas,
        },
    )


@login_required
def painel_view(request: HttpRequest) -> HttpResponse:
    """
    Painel pessoal: solicitações + minhas análises + revisões pendentes.
    """
    from datetime import UTC, datetime

    from apps.acervo.models import Analise, Revisao

    from .models import SolicitacaoCadastro

    user = request.user

    minhas_analises = (
        Analise.objects.filter(analista=user)
        .select_related("artigo")
        .order_by("-criado_em")
    )
    n_rascunhos = sum(
        1
        for a in minhas_analises
        if a.status in (Analise.Status.RASCUNHO, Analise.Status.SUBMETIDA)
    )

    revisoes_pendentes = (
        Revisao.objects.filter(revisor=user, concluido_em__isnull=True)
        .select_related("resenha__analise__artigo")
        .order_by("prazo_em")
    )
    revisoes_concluidas = (
        Revisao.objects.filter(revisor=user, concluido_em__isnull=False)
        .select_related("resenha__analise__artigo")
        .order_by("-concluido_em")[:10]
    )
    solicitacoes = (
        SolicitacaoCadastro.objects.filter(usuario=user)
        .order_by("tipo", "-criado_em")
    )

    # ── Contexto da triagem (import lazy p/ evitar ciclo) ──────────────
    contexto_triagem = {}
    if getattr(user, "eh_analista", False):
        from apps.acervo.models import Artigo
        from apps.triagem.aprovacao import registros_para_desempate
        from apps.triagem.models import (
            DecisaoTriagem,
            ProtocoloTriagem,
            RegistroTriagem,
        )

        protocolo = ProtocoloTriagem.ativo()
        triagens_pendentes = (
            DecisaoTriagem.objects.filter(revisor=user, concluido_em__isnull=True)
            .select_related("registro")
            .order_by("prazo_em")
        )
        ja_minhas = Analise.objects.filter(analista=user).values_list(
            "artigo_id", flat=True
        )
        n_a_analisar = (
            Artigo.objects.filter(
                registros_triagem__status=RegistroTriagem.Status.INCLUIDO
            )
            .exclude(pk__in=ja_minhas)
            .distinct()
            .count()
        )
        contexto_triagem = {
            "protocolo_triagem": protocolo,
            "triagens_pendentes": triagens_pendentes,
            "n_triagens": triagens_pendentes.count(),
            "n_a_analisar": n_a_analisar,
        }
        if user.is_staff or getattr(user, "eh_curador", False):
            contexto_triagem["n_identificados"] = protocolo.registros.filter(
                status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
            ).count()
            contexto_triagem["n_desempates"] = len(
                registros_para_desempate(protocolo)
            )

    return render(
        request,
        "core/painel.html",
        {
            "minhas_analises": minhas_analises,
            "n_rascunhos": n_rascunhos,
            "revisoes_pendentes": revisoes_pendentes,
            "revisoes_concluidas": revisoes_concluidas,
            "solicitacoes": solicitacoes,
            "agora": datetime.now(tz=UTC),
            **contexto_triagem,
        },
    )


@login_required
def pos_login_view(request: HttpRequest) -> HttpResponse:
    """
    Redireciona pós-login:

    - Perfil incompleto → /perfil/?onboarding=1
    - Caso contrário    → /painel/ (mostra estado das solicitações)
    """
    user = request.user
    if not user.perfil_completo_minimo:
        return redirect(f"{request.build_absolute_uri('/perfil/')}?onboarding=1")
    return redirect("painel")
