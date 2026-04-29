"""
Widgets do dashboard do admin home (Fase 6).

Em vez de uma tela custom, anexa um sumario de saude da plataforma ao
template `admin/index.html` via override do `admin.site.index`.

Tudo escopado: cuida apenas de:
- Totais de analises por status
- Revisoes pendentes vs atrasadas
- Artigos com link quebrado
- Solicitacoes de cadastro pendentes
"""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count
from django.utils import timezone


def calcular_metricas() -> dict:
    """Calcula as metricas exibidas no dashboard. Sem cache (evolui se preciso)."""
    from apps.acervo.models import Analise, Artigo, Revisao
    from apps.core.models import SolicitacaoCadastro

    agora = timezone.now()

    analises_por_status = dict(Analise.objects.values_list("status").annotate(count=Count("id")))

    revisoes_pendentes = Revisao.objects.filter(concluido_em__isnull=True).count()
    revisoes_atrasadas = Revisao.objects.filter(
        concluido_em__isnull=True,
        prazo_em__lt=agora,
    ).count()

    links_quebrados = Artigo.objects.filter(
        link_status=Artigo.LinkStatus.QUEBRADO,
    ).count()

    solicitacoes_pendentes = SolicitacaoCadastro.objects.filter(
        status=SolicitacaoCadastro.Status.PENDENTE,
    ).count()

    return {
        "analises_por_status": analises_por_status,
        "revisoes_pendentes": revisoes_pendentes,
        "revisoes_atrasadas": revisoes_atrasadas,
        "links_quebrados": links_quebrados,
        "solicitacoes_pendentes": solicitacoes_pendentes,
    }


def instalar_dashboard() -> None:
    """Patches admin.site.index para injetar `dashboard` no contexto.

    Idempotente: se ja foi instalado, no-op.
    """
    if getattr(admin.site.index, "_anco_dashboard_installed", False):
        return

    original = admin.site.index

    def index_com_dashboard(request, extra_context=None):
        ctx = dict(extra_context or {})
        try:
            ctx["dashboard"] = calcular_metricas()
        except Exception:  # noqa: BLE001
            ctx["dashboard"] = None
        return original(request, extra_context=ctx)

    index_com_dashboard._anco_dashboard_installed = True
    admin.site.index = index_com_dashboard
    admin.site.site_header = "AnCo · Curadoria"
    admin.site.site_title = "AnCo Admin"
    admin.site.index_title = "Painel de curadoria"
    admin.site.index_template = "admin/index_anco.html"
