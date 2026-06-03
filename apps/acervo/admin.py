"""Admin do app acervo."""

from django.contrib import admin, messages
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from .models import Analise, Artigo, ComentarioRevisao, Revisao, SnapshotLink
from .services import aplicar_resultado_no_artigo, capturar_snapshot_wayback, validar_link


class SnapshotLinkInline(UnfoldTabularInline):
    model = SnapshotLink
    extra = 0
    readonly_fields = ("capturado_em",)


@admin.register(Artigo)
class ArtigoAdmin(UnfoldModelAdmin):
    list_display = (
        "titulo_curto",
        "ano",
        "titulo_periodico_curto",
        "base_consulta",
        "link_status",
        "tem_link",
        "eh_legado",
    )
    list_filter = (
        "link_status",
        "eh_legado",
        "acesso_aberto",
        "artigo_pago",
        "ano",
        "base_consulta",
    )
    search_fields = ("titulo", "titulo_periodico", "doi", "autores")
    autocomplete_fields = ("base_consulta",)
    readonly_fields = ("criado_em", "atualizado_em", "link_ultima_verificacao")
    inlines = [SnapshotLinkInline]
    list_per_page = 50
    actions = (
        "verificar_link_selecionados",
        "promover_snapshot_wayback",
        "marcar_como_indisponivel",
    )

    @admin.display(description="Título", ordering="titulo")
    def titulo_curto(self, obj: Artigo) -> str:
        return (obj.titulo or "")[:90]

    @admin.display(description="Periódico", ordering="titulo_periodico")
    def titulo_periodico_curto(self, obj: Artigo) -> str:
        return (obj.titulo_periodico or "")[:60]

    @admin.display(boolean=True, description="Tem link?")
    def tem_link(self, obj: Artigo) -> bool:
        return obj.tem_link

    @admin.action(description="Re-verificar link (HEAD) dos selecionados")
    def verificar_link_selecionados(self, request, queryset):
        ok = quebrado = 0
        for artigo in queryset:
            if not artigo.link_acesso:
                continue
            resultado = validar_link(artigo.link_acesso)
            aplicar_resultado_no_artigo(artigo, resultado)
            if resultado.status == "ok":
                ok += 1
            elif resultado.status == "quebrado":
                quebrado += 1
        self.message_user(
            request,
            f"Verificados {queryset.count()} artigos: {ok} ok, {quebrado} quebrados.",
            level=messages.INFO,
        )

    @admin.action(description="Promover snapshot Wayback como link primário")
    def promover_snapshot_wayback(self, request, queryset):
        promovidos = sem_snapshot = 0
        for artigo in queryset:
            snap = artigo.snapshots.order_by("-capturado_em").first()
            if snap is None:
                # tenta capturar agora
                snap = capturar_snapshot_wayback(artigo, artigo.link_acesso)
            if snap is None:
                sem_snapshot += 1
                continue
            artigo.link_acesso = snap.url_wayback
            artigo.link_status = Artigo.LinkStatus.OK
            artigo.link_ultima_verificacao = timezone.now()
            artigo.save(
                update_fields=["link_acesso", "link_status", "link_ultima_verificacao"],
            )
            promovidos += 1
        self.message_user(
            request,
            f"{promovidos} promovido(s); {sem_snapshot} sem snapshot disponível.",
            level=messages.INFO,
        )

    @admin.action(description="Marcar como indisponível permanentemente (link_status=quebrado)")
    def marcar_como_indisponivel(self, request, queryset):
        atualizados = queryset.update(
            link_status=Artigo.LinkStatus.QUEBRADO,
            link_ultima_verificacao=timezone.now(),
        )
        self.message_user(
            request,
            f"{atualizados} artigo(s) marcado(s) como indisponíveis.",
            level=messages.WARNING,
        )


# ---------------------------------------------------------------------------
# Proxy "Links Quebrados" — changelist ja filtrada para a curadoria
# ---------------------------------------------------------------------------


class LinkQuebrado(Artigo):
    """Proxy de Artigo: atalho no admin so com link_status='quebrado'."""

    class Meta:
        proxy = True
        verbose_name = "link quebrado"
        verbose_name_plural = "links quebrados"


@admin.register(LinkQuebrado)
class LinkQuebradoAdmin(ArtigoAdmin):
    """Mesma admin de Artigo, mas filtrada por link_status='quebrado'."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(link_status=Artigo.LinkStatus.QUEBRADO)


class ComentarioRevisaoInline(UnfoldTabularInline):
    model = ComentarioRevisao
    extra = 0
    readonly_fields = ("criado_em",)


@admin.register(Revisao)
class RevisaoAdmin(UnfoldModelAdmin):
    list_display = ("id", "analise", "revisor", "tipo", "parecer", "prazo_em", "concluido_em")
    list_filter = ("tipo", "parecer")
    search_fields = ("analise__artigo__titulo", "revisor__username")
    autocomplete_fields = ("analise", "revisor")
    readonly_fields = ("sorteado_em",)
    inlines = [ComentarioRevisaoInline]


class RevisaoInline(UnfoldTabularInline):
    model = Revisao
    extra = 0
    fields = ("revisor", "tipo", "parecer", "prazo_em", "concluido_em")
    readonly_fields = ("sorteado_em",)
    show_change_link = True
    autocomplete_fields = ("revisor",)


@admin.register(Analise)
class AnaliseAdmin(SimpleHistoryAdmin, UnfoldModelAdmin):
    list_display = ("id", "artigo", "analista", "status", "tem_resenha", "criado_em")
    list_filter = ("status", "tem_resenha", "criado_em")
    search_fields = ("artigo__titulo", "analista__username", "objeto", "objetivo")
    autocomplete_fields = ("artigo", "analista")
    readonly_fields = ("criado_em", "submetida_em", "publicada_em", "tem_resenha")
    filter_horizontal = ("epistemologia", "teoria")
    inlines = [RevisaoInline]
    list_per_page = 50

    fieldsets = (
        (None, {"fields": ("artigo", "analista", "status")}),
        (
            "Presença do termo AnCo",
            {
                "fields": (
                    "presenca_titulo",
                    "presenca_resumo",
                    "presenca_palavras_chave",
                    "presenca_referencias",
                    "presenca_corpo",
                ),
            },
        ),
        (
            "Pertinência",
            {
                "fields": (
                    "pertinencia",
                    "aspectos_relevantes",
                    "define_conceito",
                    "definicao_extraida",
                )
            },
        ),
        (
            "Estrutura do artigo",
            {
                "fields": (
                    "objeto",
                    "objetivo",
                    "foco",
                    "metodologia",
                    "epistemologia",
                    "teoria",
                    "referenciais",
                    "resultados",
                ),
            },
        ),
        ("Contexto e observações", {"fields": ("contexto_producao", "observacoes")}),
        ("Resenha crítica autoral", {"fields": ("resenha_critica", "tem_resenha")}),
        ("Datas", {"fields": ("criado_em", "submetida_em", "publicada_em")}),
    )


@admin.register(SnapshotLink)
class SnapshotLinkAdmin(UnfoldModelAdmin):
    list_display = ("id", "artigo", "capturado_em")
    search_fields = ("artigo__titulo", "url_original", "url_wayback")
    autocomplete_fields = ("artigo",)


@admin.register(ComentarioRevisao)
class ComentarioRevisaoAdmin(UnfoldModelAdmin):
    list_display = ("id", "revisao", "campo", "criado_em")
    search_fields = ("texto", "campo")
    autocomplete_fields = ("revisao",)
