"""Views da triagem PRISMA-ScR.

Fase 9.0 — scaffolding: um painel placeholder gated a analistas/curadores,
só para confirmar o wiring da URL. As telas reais (importar, registros,
triar, minhas-triagens, desempate, PRISMA) entram nas Fases 9.2/9.4/9.6.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render


@login_required
def painel_view(request: HttpRequest) -> HttpResponse:
    if not getattr(request.user, "eh_analista", False):
        return HttpResponseForbidden(
            "Apenas analistas ou curadores acessam a triagem."
        )
    return render(request, "triagem/painel.html")
