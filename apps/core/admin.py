"""Admin do app core."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import SolicitacaoCadastro, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "nome_exibicao",
        "papel",
        "vinculo_institucional",
        "aceita_revisoes",
        "eh_legado",
        "is_active",
    )
    list_filter = (
        "papel",
        "aceita_revisoes",
        "eh_legado",
        "is_active",
        "is_staff",
    )
    search_fields = ("username", "email", "nome_exibicao", "vinculo_institucional", "orcid")

    fieldsets = (
        *DjangoUserAdmin.fieldsets,
        (
            "Perfil AnCo",
            {
                "fields": (
                    "nome_exibicao",
                    "vinculo_institucional",
                    "grupo_pesquisa",
                    "orcid",
                    "papel",
                    "aceita_revisoes",
                    "limite_revisoes_simultaneas",
                    "eh_legado",
                )
            },
        ),
    )


@admin.register(SolicitacaoCadastro)
class SolicitacaoCadastroAdmin(admin.ModelAdmin):
    list_display = ("usuario", "status", "revisado_por", "revisado_em", "criado_em")
    list_filter = ("status",)
    search_fields = ("usuario__username", "usuario__email", "justificativa")
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("usuario", "revisado_por")
