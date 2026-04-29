"""Admin do app vocabulario."""

from django.contrib import admin

from .models import TermoVocabulario, Vocabulario


class TermoInline(admin.TabularInline):
    model = TermoVocabulario
    fields = ("nome", "ativo", "sinonimos")
    extra = 0
    show_change_link = True


@admin.register(Vocabulario)
class VocabularioAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo", "criado_em")
    search_fields = ("nome", "codigo")
    prepopulated_fields = {"codigo": ("nome",)}
    inlines = [TermoInline]


@admin.register(TermoVocabulario)
class TermoVocabularioAdmin(admin.ModelAdmin):
    list_display = ("nome", "vocabulario", "ativo", "criado_em")
    list_filter = ("vocabulario", "ativo")
    search_fields = ("nome", "sinonimos", "vocabulario__nome")
    autocomplete_fields = ("vocabulario",)
    list_editable = ("ativo",)
