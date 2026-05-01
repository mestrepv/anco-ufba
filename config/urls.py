"""URL configuration do projeto AnCo."""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import include, path

from apps.core.views import consultar_doi_view, promocao_status_view, solicitar_promocao_view, teste_design_view
from apps.publico.urls import urlpatterns_acervo, urlpatterns_root
from apps.publico.views import vitrine_view


def healthcheck(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthcheck, name="healthz"),
    path("", vitrine_view, name="home"),
    path("accounts/", include("allauth.urls")),
    path("cadastro/promocao/", solicitar_promocao_view, name="solicitar_promocao"),
    path("cadastro/promocao/status/", promocao_status_view, name="promocao_status"),
    # URLs publicas com forma estavel para citacoes (/artigo/<slug>/, /analise/<id>/)
    *urlpatterns_root,
    # Listagem publica em /acervo/ (root) — analyst views ficam em /acervo-analista/
    path("acervo/", include(urlpatterns_acervo)),
    # Fluxos de analista permanecem em /acervo-analista/ apos a Fase 5
    path("acervo-analista/", include("apps.acervo.urls")),
    # Página de teste do design system — remover antes do go-live público
    path("_design/", teste_design_view, name="teste_design"),
    path("_ferramentas/doi/", consultar_doi_view, name="consultar_doi"),
]
