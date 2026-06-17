"""Rotas do módulo Revisão ANCO. Montadas em /anco/ (só quando ANCO_ATIVO)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.projetos_view, name="anco_projetos"),
    path("p/<slug:slug>/", views.painel_view, name="anco_painel"),
    path("p/<slug:slug>/importar/", views.importar_view, name="anco_importar"),
    path(
        "p/<slug:slug>/fonte/<int:fonte_id>/excluir/",
        views.fonte_excluir_view,
        name="anco_fonte_excluir",
    ),
    path("p/<slug:slug>/corpus/", views.corpus_view, name="anco_corpus"),
    path("p/<slug:slug>/corpus/excluir/", views.corpus_excluir_view, name="anco_corpus_excluir"),
    path(
        "p/<slug:slug>/corpus/<int:item_id>/editar/",
        views.corpus_editar_view,
        name="anco_corpus_editar",
    ),
    path("p/<slug:slug>/sorteio/", views.sorteio_view, name="anco_sorteio"),
    path(
        "p/<slug:slug>/sorteio/elegiveis/",
        views.sorteio_elegiveis_view,
        name="anco_sorteio_elegiveis",
    ),
    path("p/<slug:slug>/estatisticas/", views.estatisticas_view, name="anco_estatisticas"),
    path("p/<slug:slug>/equipe/", views.equipe_view, name="anco_equipe"),
]
