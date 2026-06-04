"""Admin (Unfold) da triagem PRISMA-ScR."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from .models import Busca, DecisaoTriagem, ProtocoloTriagem, RegistroTriagem


@admin.register(ProtocoloTriagem)
class ProtocoloTriagemAdmin(UnfoldModelAdmin):
    list_display = ("titulo", "n_revisores", "prazo_dias", "atualizado_em")
    search_fields = ("titulo",)
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(Busca)
class BuscaAdmin(UnfoldModelAdmin):
    list_display = ("base_nome", "n_identificados", "data_busca", "criado_por", "criado_em")
    list_filter = ("formato", "base_consulta")
    search_fields = ("outra_base", "string_busca")
    autocomplete_fields = ("base_consulta", "criado_por")
    readonly_fields = ("criado_em",)


class DecisaoTriagemInline(UnfoldTabularInline):
    model = DecisaoTriagem
    extra = 0
    fields = ("revisor", "decisao", "prazo_em", "concluido_em")
    readonly_fields = ("sorteado_em",)
    autocomplete_fields = ("revisor",)
    show_change_link = True


@admin.register(RegistroTriagem)
class RegistroTriagemAdmin(SimpleHistoryAdmin, UnfoldModelAdmin):
    list_display = ("titulo_curto", "status", "ano", "ja_no_acervo", "criado_em")
    list_filter = ("status", "ja_no_acervo", "protocolo")
    search_fields = ("titulo", "doi", "isbn", "autores")
    autocomplete_fields = ("protocolo", "artigo", "duplicado_de", "decidida_por")
    readonly_fields = ("identificador", "criado_em")
    inlines = [DecisaoTriagemInline]

    @admin.display(description="título")
    def titulo_curto(self, obj: RegistroTriagem) -> str:
        return obj.titulo[:80]


@admin.register(DecisaoTriagem)
class DecisaoTriagemAdmin(UnfoldModelAdmin):
    list_display = ("registro", "revisor", "decisao", "prazo_em", "concluido_em")
    list_filter = ("decisao",)
    search_fields = ("registro__titulo", "revisor__email")
    autocomplete_fields = ("registro", "revisor")
    readonly_fields = ("sorteado_em",)
