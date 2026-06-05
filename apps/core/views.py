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

    # ── Contexto da triagem (import lazy p/ evitar ciclo) ──────────────
    contexto_triagem = {}
    if getattr(user, "eh_analista", False):
        from django.urls import reverse

        from apps.acervo.models import Artigo
        from apps.triagem.aprovacao import registros_para_desempate
        from apps.triagem.duplicatas import contar_pares_do_usuario
        from apps.triagem.models import (
            DecisaoTriagem,
            ProtocoloTriagem,
            RegistroTriagem,
        )

        # Projeto ativo do usuário (Fase 12): 1º não arquivado em que é membro.
        projetos_qs = ProtocoloTriagem.objects.filter(arquivado=False)
        if not user.is_staff:
            projetos_qs = projetos_qs.filter(membros__usuario=user).distinct()
        meus_projetos = list(projetos_qs.order_by("nome"))
        protocolo = meus_projetos[0] if meus_projetos else None

        # Trabalho do revisor é global (atravessa projetos).
        triagens_pendentes = (
            DecisaoTriagem.objects.filter(revisor=user, concluido_em__isnull=True)
            .select_related("registro")
            .order_by("prazo_em")
        )
        n_triagens = triagens_pendentes.count()
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

        if protocolo is not None:
            sl = protocolo.slug
            eh_curador = protocolo.eh_curador_no(user)
            # Conta só as duplicatas que o usuário pode resolver (alinha com a
            # tela, que aplica o gate importador/curador da Fase 12.4).
            n_duplicatas = contar_pares_do_usuario(protocolo, user, eh_curador)
            n_identificados = (
                protocolo.registros.filter(
                    status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
                ).count()
                if eh_curador
                else 0
            )
            n_desempates = len(registros_para_desempate(protocolo)) if eh_curador else 0

            # Mapa do fluxo (etapas clicáveis, com contagem onde há trabalho).
            passos = [
                {"num": 1, "titulo": "Importar base", "href": reverse("triagem_importar", args=[sl]),
                 "count": None, "curador": False},
                {"num": 2, "titulo": "Revisar duplicatas", "href": reverse("triagem_duplicatas", args=[sl]),
                 "count": n_duplicatas or None, "curador": False},
                {"num": 3, "titulo": "Iniciar triagem", "href": reverse("triagem_iniciar", args=[sl]),
                 "count": n_identificados or None, "curador": True},
                {"num": 4, "titulo": "Triar", "href": reverse("triagem_minhas"),
                 "count": n_triagens or None, "curador": False},
                {"num": 5, "titulo": "Desempates", "href": reverse("triagem_desempate", args=[sl]),
                 "count": n_desempates or None, "curador": True},
                {"num": 6, "titulo": "A analisar", "href": reverse("triagem_a_analisar"),
                 "count": n_a_analisar or None, "curador": False},
                {"num": 7, "titulo": "Acompanhar (PRISMA)", "href": reverse("triagem_prisma", args=[sl]),
                 "count": None, "curador": False},
            ]
        else:
            sl = None
            eh_curador = False
            n_duplicatas = n_identificados = n_desempates = 0
            passos = []

        # Próximo passo: a única coisa óbvia a fazer agora (por prioridade).
        if n_triagens:
            proxima = {"titulo": f"Você tem {n_triagens} triagem(ns) para fazer",
                       "sub": "Decida incluir ou excluir cada registro sorteado para você.",
                       "href": reverse("triagem_minhas"), "label": "Triar agora"}
        elif eh_curador and n_desempates:
            proxima = {"titulo": f"{n_desempates} desempate(s) aguardando você",
                       "sub": "Revisores divergiram — defina a decisão final.",
                       "href": reverse("triagem_desempate", args=[sl]), "label": "Resolver desempates"}
        elif n_a_analisar:
            proxima = {"titulo": f"{n_a_analisar} artigo(s) prontos para análise",
                       "sub": "Preencha a Matriz AnCo dos artigos selecionados pela triagem.",
                       "href": reverse("triagem_a_analisar"), "label": "Analisar"}
        elif protocolo is not None and n_duplicatas:
            proxima = {"titulo": f"{n_duplicatas} possível(is) duplicata(s) para revisar",
                       "sub": "Confirme quais registros são o mesmo trabalho antes de triar.",
                       "href": reverse("triagem_duplicatas", args=[sl]), "label": "Revisar duplicatas"}
        elif eh_curador and n_identificados:
            proxima = {"titulo": f"{n_identificados} registro(s) prontos para a triagem",
                       "sub": "Feche a coleta e sorteie os revisores.",
                       "href": reverse("triagem_iniciar", args=[sl]), "label": "Iniciar triagem"}
        elif n_rascunhos:
            proxima = {"titulo": f"{n_rascunhos} análise(s) em andamento",
                       "sub": "Continue de onde parou.",
                       "href": reverse("minhas_analises"), "label": "Continuar"}
        elif protocolo is not None:
            proxima = {"titulo": "Tudo em dia 🎉",
                       "sub": "Importe uma nova base para começar uma rodada de triagem.",
                       "href": reverse("triagem_importar", args=[sl]), "label": "Importar busca"}
        else:
            proxima = None

        contexto_triagem = {
            "protocolo_triagem": protocolo,
            "meus_projetos": meus_projetos,
            "n_projetos": len(meus_projetos),
            "triagens_pendentes": triagens_pendentes,
            "n_triagens": n_triagens,
            "n_a_analisar": n_a_analisar,
            "n_duplicatas": n_duplicatas,
            "n_identificados": n_identificados,
            "n_desempates": n_desempates,
            "passos": passos,
            "proxima": proxima,
            "eh_curador_painel": eh_curador,
        }

    return render(
        request,
        "core/painel.html",
        {
            "minhas_analises": minhas_analises,
            "n_rascunhos": n_rascunhos,
            "revisoes_pendentes": revisoes_pendentes,
            "revisoes_concluidas": revisoes_concluidas,
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
