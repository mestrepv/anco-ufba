"""Rotas da triagem PRISMA-ScR. Montadas em /triagem/ (config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel_view, name="triagem_painel"),
    path("importar/", views.importar_view, name="triagem_importar"),
    path("registros/", views.registros_view, name="triagem_registros"),
]
