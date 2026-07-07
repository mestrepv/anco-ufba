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
    # Editar os metadados do artigo da análise (completar campos da importação).
    path(
        "analise/<int:analise_id>/artigo/editar/",
        views.editar_metadados_artigo_view,
        name="editar_metadados_artigo",
    ),
    # Visualização (curador) da análise de um analista — mesma tela, só leitura.
    # Por (artigo, analista): funciona mesmo se o analista ainda não iniciou.
    path(
        "ver/<int:artigo_id>/analista/<int:analista_id>/",
        views.ver_analise_analista_view,
        name="ver_analise_analista",
    ),
    path(
        "analise/<int:analise_id>/submeter/",
        views.submeter_analise_view,
        name="submeter_analise",
    ),
    path(
        "analise/<int:analise_id>/excluir/",
        views.excluir_analise_view,
        name="excluir_analise",
    ),
    # Resenha crítica (entidade própria, sujeita a revisão cega)
    path(
        "analise/<int:analise_id>/resenha/",
        views.editar_resenha_view,
        name="editar_resenha",
    ),
    path(
        "analise/<int:analise_id>/resenha/autosave/",
        views.autosave_resenha_view,
        name="autosave_resenha",
    ),
    path(
        "analise/<int:analise_id>/resenha/submeter/",
        views.submeter_resenha_view,
        name="submeter_resenha",
    ),
    # Revisão cega por pares (da resenha)
    path("revisoes/", views.minhas_revisoes_view, name="minhas_revisoes"),
    path("revisao/<int:revisao_id>/", views.revisar_view, name="revisar"),
    # Curadoria
    path("curadoria/", views.fila_curadoria_view, name="fila_curadoria"),
    path(
        "curadoria/analise/<int:analise_id>/aprovar/",
        views.aprovar_analise_view,
        name="aprovar_analise",
    ),
    path(
        "curadoria/analise/<int:analise_id>/devolver/",
        views.devolver_analise_view,
        name="devolver_analise",
    ),
    path(
        "curadoria/resenha/<int:resenha_id>/confirmar/",
        views.confirmar_resenha_view,
        name="confirmar_resenha",
    ),
    path(
        "curadoria/resenha/<int:resenha_id>/rejeitar/",
        views.rejeitar_resenha_view,
        name="rejeitar_resenha",
    ),
    path(
        "curadoria/analise/<int:analise_id>/despublicar/",
        views.despublicar_analise_view,
        name="despublicar_analise",
    ),
    path(
        "curadoria/analise/<int:analise_id>/restaurar/",
        views.restaurar_analise_view,
        name="restaurar_analise",
    ),
]
