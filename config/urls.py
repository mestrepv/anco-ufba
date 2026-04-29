"""URL configuration do projeto AnCo."""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import include, path

from apps.core.views import home_view, promocao_status_view, solicitar_promocao_view


def healthcheck(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthcheck, name="healthz"),
    path("", home_view, name="home"),
    path("accounts/", include("allauth.urls")),
    path("cadastro/promocao/", solicitar_promocao_view, name="solicitar_promocao"),
    path("cadastro/promocao/status/", promocao_status_view, name="promocao_status"),
    path("acervo/", include("apps.acervo.urls")),
]
