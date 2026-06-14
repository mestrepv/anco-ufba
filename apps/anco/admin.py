from django.contrib import admin

from .models import (
    AtribuicaoANCO,
    ConsensoANCO,
    FonteImport,
    ItemCorpus,
    MembroANCO,
    ProjetoANCO,
    SorteioANCO,
)


class MembroANCOInline(admin.TabularInline):
    model = MembroANCO
    extra = 0
    autocomplete_fields = ["usuario"]


@admin.register(ProjetoANCO)
class ProjetoANCOAdmin(admin.ModelAdmin):
    list_display = ["nome", "slug", "arquivado", "criado_em"]
    prepopulated_fields = {"slug": ["nome"]}
    search_fields = ["nome", "slug"]
    inlines = [MembroANCOInline]


@admin.register(FonteImport)
class FonteImportAdmin(admin.ModelAdmin):
    list_display = ["__str__", "projeto", "n_novos", "importado_em", "criado_por"]
    list_filter = ["projeto"]


@admin.register(ItemCorpus)
class ItemCorpusAdmin(admin.ModelAdmin):
    list_display = ["titulo", "projeto", "ano", "removido", "criado_em"]
    list_filter = ["projeto", "removido"]
    search_fields = ["titulo", "doi", "autores"]


admin.site.register(SorteioANCO)
admin.site.register(AtribuicaoANCO)
admin.site.register(ConsensoANCO)
