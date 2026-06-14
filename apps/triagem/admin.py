"""Admin (Unfold) da triagem PRISMA-ScR."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from .models import (
    Busca,
    DecisaoTriagem,
    ProjetoMembro,
    ProtocoloTriagem,
    RegistroTriagem,
    RodadaCalibracao,
    SnapshotProtocolo,
)


class ProjetoMembroInline(UnfoldTabularInline):
    model = ProjetoMembro
    extra = 0
    fields = ("usuario", "papel", "criado_em")
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("usuario",)


class SnapshotProtocoloInline(UnfoldTabularInline):
    model = SnapshotProtocolo
    extra = 0
    fields = ("versao", "travado_por", "criado_em")
    readonly_fields = ("versao", "dados", "travado_por", "criado_em")
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ProtocoloTriagem)
class ProtocoloTriagemAdmin(UnfoldModelAdmin):
    list_display = (
        "nome",
        "slug",
        "arquivado",
        "versao",
        "usa_texto_completo",
        "travado_em",
        "n_revisores",
        "atualizado_em",
    )
    list_filter = ("arquivado", "usa_texto_completo")
    search_fields = ("nome", "titulo", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    readonly_fields = ("versao", "travado_em", "criado_em", "atualizado_em")
    inlines = [ProjetoMembroInline, SnapshotProtocoloInline]


@admin.register(ProjetoMembro)
class ProjetoMembroAdmin(UnfoldModelAdmin):
    list_display = ("projeto", "usuario", "papel", "criado_em")
    list_filter = ("papel", "projeto")
    search_fields = ("usuario__email", "usuario__nome_exibicao", "projeto__nome")
    autocomplete_fields = ("projeto", "usuario")


@admin.register(SnapshotProtocolo)
class SnapshotProtocoloAdmin(UnfoldModelAdmin):
    list_display = ("protocolo", "versao", "travado_por", "criado_em")
    list_filter = ("protocolo",)
    readonly_fields = ("protocolo", "versao", "dados", "travado_por", "criado_em")

    def has_add_permission(self, request) -> bool:
        return False


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
    autocomplete_fields = ("protocolo", "artigo", "duplicado_de", "duplicado_por", "decidida_por")
    readonly_fields = ("identificador", "criado_em", "duplicado_em")
    inlines = [DecisaoTriagemInline]

    @admin.display(description="título")
    def titulo_curto(self, obj: RegistroTriagem) -> str:
        return obj.titulo[:80]


@admin.register(DecisaoTriagem)
class DecisaoTriagemAdmin(UnfoldModelAdmin):
    list_display = ("registro", "revisor", "etapa", "decisao", "prazo_em", "concluido_em")
    list_filter = ("etapa", "decisao")
    search_fields = ("registro__titulo", "revisor__email")
    autocomplete_fields = ("registro", "revisor")
    readonly_fields = ("sorteado_em",)


@admin.register(RodadaCalibracao)
class RodadaCalibracaoAdmin(UnfoldModelAdmin):
    list_display = ("pk", "protocolo", "n_itens", "n_revisores", "kappa", "fechada_em", "criada_em")
    list_filter = ("protocolo",)
    readonly_fields = ("criada_em", "fechada_em", "n_itens", "n_revisores", "perc_acordo", "kappa")
    filter_horizontal = ("registros",)

