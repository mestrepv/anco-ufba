"""URLs publicas (Fase 5).

Note que algumas URLs sao montadas no root (config/urls.py) para terem
forma estavel e citavel: /artigo/<slug>/ e /analise/<id>/.
"""

from django.urls import path

from . import views

# URLs publicas que podem ser montadas em /acervo/.
urlpatterns_acervo = [
    path("", views.listagem_view, name="acervo_publico"),
]

# URLs root (citacoes estaveis).
urlpatterns_root = [
    path("artigo/<str:doi_slug>/", views.pagina_artigo_view, name="pagina_artigo"),
    path("analise/<int:analise_id>/", views.pagina_analise_view, name="pagina_analise"),
    path(
        "analise/<int:analise_id>/historico/",
        views.historico_analise_view,
        name="historico_analise",
    ),
    # Paginas institucionais (Fase 7)
    path("sobre/", views.pagina_sobre_view, name="pagina_sobre"),
    path("equipe/", views.pagina_equipe_view, name="pagina_equipe"),
    path("termos/", views.pagina_termos_view, name="pagina_termos"),
    path("privacidade/", views.pagina_privacidade_view, name="pagina_privacidade"),
    # SEO
    path("robots.txt", views.robots_txt_view, name="robots"),
    path("sitemap.xml", views.sitemap_view, name="sitemap"),
]
