"""Rotas da triagem PRISMA-ScR. Montadas em /triagem/ (config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel_view, name="triagem_painel"),
    path("importar/", views.importar_view, name="triagem_importar"),
    path("registros/", views.registros_view, name="triagem_registros"),
    path("iniciar/", views.iniciar_triagem_view, name="triagem_iniciar"),
    path("minhas/", views.minhas_triagens_view, name="triagem_minhas"),
    path("triar/<int:decisao_id>/", views.triar_view, name="triagem_triar"),
    path("desempate/", views.fila_desempate_view, name="triagem_desempate"),
    path("desempate/<int:registro_id>/", views.desempatar_view, name="triagem_desempatar"),
    path("prisma/", views.prisma_view, name="triagem_prisma"),
]
