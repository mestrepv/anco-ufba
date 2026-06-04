"""Rotas da triagem PRISMA-ScR. Montadas em /triagem/ (config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel_view, name="triagem_painel"),
    path("ajuda/", views.ajuda_view, name="triagem_ajuda"),
    path("importar/", views.importar_view, name="triagem_importar"),
    path("busca/<int:busca_id>/", views.busca_resumo_view, name="triagem_busca_resumo"),
    path("registros/", views.registros_view, name="triagem_registros"),
    path("duplicatas/", views.duplicatas_view, name="triagem_duplicatas"),
    path("duplicatas/mesclar/", views.mesclar_duplicata_view, name="triagem_duplicata_mesclar"),
    path("duplicatas/descartar/", views.descartar_duplicata_view, name="triagem_duplicata_descartar"),
    path("iniciar/", views.iniciar_triagem_view, name="triagem_iniciar"),
    path("minhas/", views.minhas_triagens_view, name="triagem_minhas"),
    path("triar/<int:decisao_id>/", views.triar_view, name="triagem_triar"),
    path("desempate/", views.fila_desempate_view, name="triagem_desempate"),
    path("desempate/<int:registro_id>/", views.desempatar_view, name="triagem_desempatar"),
    path("a-analisar/", views.a_analisar_view, name="triagem_a_analisar"),
    path("prisma/", views.prisma_view, name="triagem_prisma"),
]
