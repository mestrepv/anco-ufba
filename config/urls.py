"""URL configuration do projeto AnCo."""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path


def healthcheck(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthcheck, name="healthz"),
]
