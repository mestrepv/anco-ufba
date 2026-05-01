"""URLs do app acervo (Fase 3)."""

from django.urls import path

from . import views

urlpatterns = [
    path("minhas/", views.minhas_analises_view, name="minhas_analises"),
    path("buscar/", views.buscar_artigo_view, name="buscar_artigo"),
    path("artigo/novo/", views.cadastrar_artigo_view, name="cadastrar_artigo"),
    path(
        "artigo/lookup/",
        views.lookup_identificador_view,
        name="lookup_identificador",
    ),
    path(
        "artigo/<int:artigo_id>/snapshot/",
        views.capturar_snapshot_view,
        name="capturar_snapshot",
    ),
    path(
        "artigo/<int:artigo_id>/iniciar-analise/",
        views.iniciar_analise_view,
        name="iniciar_analise",
    ),
    path(
        "analise/<int:analise_id>/editar/",
        views.editar_analise_view,
        name="editar_analise",
    ),
    path(
        "analise/<int:analise_id>/autosave/",
        views.autosave_analise_view,
        name="autosave_analise",
    ),
    path(
        "analise/<int:analise_id>/submeter/",
        views.submeter_analise_view,
        name="submeter_analise",
    ),
    # Revisao por pares (Fase 4)
    path("revisoes/", views.minhas_revisoes_view, name="minhas_revisoes"),
    path("revisao/<int:revisao_id>/", views.revisar_view, name="revisar"),
]
