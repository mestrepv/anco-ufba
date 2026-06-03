"""Admin do app vocabulario."""

from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from .models import TermoVocabulario, Vocabulario


class TermoInline(UnfoldTabularInline):
    model = TermoVocabulario
    fields = ("nome", "ativo", "sinonimos")
    extra = 0
    show_change_link = True


@admin.register(Vocabulario)
class VocabularioAdmin(UnfoldModelAdmin):
    list_display = ("nome", "codigo", "criado_em")
    search_fields = ("nome", "codigo")
    prepopulated_fields = {"codigo": ("nome",)}
    inlines = [TermoInline]


@admin.register(TermoVocabulario)
class TermoVocabularioAdmin(UnfoldModelAdmin):
    list_display = ("nome", "vocabulario", "ativo", "criado_em")
    list_filter = ("vocabulario", "ativo")
    search_fields = ("nome", "sinonimos", "vocabulario__nome")
    autocomplete_fields = ("vocabulario",)
    list_editable = ("ativo",)
