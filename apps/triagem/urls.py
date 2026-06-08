"""Rotas da triagem PRISMA-ScR. Montadas em /triagem/ (config/urls.py).

Fase 12: as rotas de um projeto vivem sob `p/<slug>/`; as rotas globais (lista de
projetos, trabalho do revisor) ficam na raiz. Caminhos antigos sem slug
redirecionam para o projeto default (compat durante a transição).
"""

from django.shortcuts import redirect
from django.urls import path

from . import views
from .models import ProtocoloTriagem


def _compat(nome):
    """Redireciona um caminho antigo (sem slug) para o projeto default."""

    def _view(request, **kwargs):
        projeto = ProtocoloTriagem.ativo()
        return redirect(nome, slug=projeto.slug, **kwargs)

    return _view


urlpatterns = [
    # ── Globais (sem projeto) ──────────────────────────────────────────────
    path("", views.projetos_view, name="triagem_projetos"),
    path("novo/", views.novo_projeto_view, name="triagem_novo_projeto"),
    path("ajuda/", views.ajuda_view, name="triagem_ajuda"),
    path("minhas/", views.minhas_triagens_view, name="triagem_minhas"),
    path("triar/<int:decisao_id>/", views.triar_view, name="triagem_triar"),
    path("a-analisar/", views.a_analisar_view, name="triagem_a_analisar"),
    # ── Por projeto ────────────────────────────────────────────────────────
    path("p/<slug:slug>/", views.painel_view, name="triagem_painel"),
    path("p/<slug:slug>/protocolo/", views.protocolo_view, name="triagem_protocolo"),
    path("p/<slug:slug>/checklist/", views.checklist_view, name="triagem_checklist"),
    path("p/<slug:slug>/calibracao/", views.calibracao_view, name="triagem_calibracao"),
    path("p/<slug:slug>/importar/", views.importar_view, name="triagem_importar"),
    path(
        "p/<slug:slug>/importar/preview/",
        views.importar_preview_view,
        name="triagem_importar_preview",
    ),
    path(
        "p/<slug:slug>/busca/<int:busca_id>/", views.busca_resumo_view, name="triagem_busca_resumo"
    ),
    path(
        "p/<slug:slug>/busca/<int:busca_id>/excluir/",
        views.excluir_busca_view,
        name="triagem_busca_excluir",
    ),
    path("p/<slug:slug>/registros/", views.registros_view, name="triagem_registros"),
    path("p/<slug:slug>/duplicatas/", views.duplicatas_view, name="triagem_duplicatas"),
    path(
        "p/<slug:slug>/duplicatas/mesclar/",
        views.mesclar_duplicata_view,
        name="triagem_duplicata_mesclar",
    ),
    path(
        "p/<slug:slug>/duplicatas/descartar/",
        views.descartar_duplicata_view,
        name="triagem_duplicata_descartar",
    ),
    path(
        "p/<slug:slug>/duplicatas/mescladas/",
        views.duplicatas_mescladas_view,
        name="triagem_duplicatas_mescladas",
    ),
    path(
        "p/<slug:slug>/duplicatas/desfazer/",
        views.desfazer_mescla_view,
        name="triagem_duplicata_desfazer",
    ),
    path("p/<slug:slug>/iniciar/", views.iniciar_triagem_view, name="triagem_iniciar"),
    path("p/<slug:slug>/autotriar/", views.autotriar_view, name="triagem_autotriar"),
    path("p/<slug:slug>/desempate/", views.fila_desempate_view, name="triagem_desempate"),
    path(
        "p/<slug:slug>/desempate/<int:registro_id>/",
        views.desempatar_view,
        name="triagem_desempatar",
    ),
    path("p/<slug:slug>/incluidos/", views.incluidos_view, name="triagem_incluidos"),
    path(
        "p/<slug:slug>/incluidos/excluir/",
        views.excluir_incluido_view,
        name="triagem_incluido_excluir",
    ),
    path(
        "p/<slug:slug>/incluir-corpus/",
        views.incluir_corpus_view,
        name="triagem_incluir_corpus",
    ),
    path("p/<slug:slug>/estatisticas/", views.estatisticas_view, name="triagem_estatisticas"),
    path(
        "p/<slug:slug>/sorteio-analise/", views.sorteio_analise_view, name="triagem_sorteio_analise"
    ),
    path("p/<slug:slug>/consenso/", views.consenso_view, name="triagem_consenso"),
    path("p/<slug:slug>/prisma/", views.prisma_view, name="triagem_prisma"),
    # ── Compat: caminhos antigos → projeto default ─────────────────────────
    path("importar/", _compat("triagem_importar")),
    path("registros/", _compat("triagem_registros")),
    path("duplicatas/", _compat("triagem_duplicatas")),
    path("prisma/", _compat("triagem_prisma")),
    path("protocolo/", _compat("triagem_protocolo")),
    path("checklist/", _compat("triagem_checklist")),
    path("calibracao/", _compat("triagem_calibracao")),
    path("iniciar/", _compat("triagem_iniciar")),
    path("desempate/", _compat("triagem_desempate")),
]
