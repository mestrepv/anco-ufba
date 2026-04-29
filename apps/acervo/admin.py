"""Admin do app acervo."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Analise, Artigo, ComentarioRevisao, Revisao, SnapshotLink


class SnapshotLinkInline(admin.TabularInline):
    model = SnapshotLink
    extra = 0
    readonly_fields = ("capturado_em",)


@admin.register(Artigo)
class ArtigoAdmin(admin.ModelAdmin):
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

    @admin.display(description="Título", ordering="titulo")
    def titulo_curto(self, obj: Artigo) -> str:
        return (obj.titulo or "")[:90]

    @admin.display(description="Periódico", ordering="titulo_periodico")
    def titulo_periodico_curto(self, obj: Artigo) -> str:
        return (obj.titulo_periodico or "")[:60]

    @admin.display(boolean=True, description="Tem link?")
    def tem_link(self, obj: Artigo) -> bool:
        return obj.tem_link


class ComentarioRevisaoInline(admin.TabularInline):
    model = ComentarioRevisao
    extra = 0
    readonly_fields = ("criado_em",)


@admin.register(Revisao)
class RevisaoAdmin(admin.ModelAdmin):
    list_display = ("id", "analise", "revisor", "tipo", "parecer", "prazo_em", "concluido_em")
    list_filter = ("tipo", "parecer")
    search_fields = ("analise__artigo__titulo", "revisor__username")
    autocomplete_fields = ("analise", "revisor")
    readonly_fields = ("sorteado_em",)
    inlines = [ComentarioRevisaoInline]


class RevisaoInline(admin.TabularInline):
    model = Revisao
    extra = 0
    fields = ("revisor", "tipo", "parecer", "prazo_em", "concluido_em")
    readonly_fields = ("sorteado_em",)
    show_change_link = True
    autocomplete_fields = ("revisor",)


@admin.register(Analise)
class AnaliseAdmin(SimpleHistoryAdmin):
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
class SnapshotLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "artigo", "capturado_em")
    search_fields = ("artigo__titulo", "url_original", "url_wayback")
    autocomplete_fields = ("artigo",)


@admin.register(ComentarioRevisao)
class ComentarioRevisaoAdmin(admin.ModelAdmin):
    list_display = ("id", "revisao", "campo", "criado_em")
    search_fields = ("texto", "campo")
    autocomplete_fields = ("revisao",)
