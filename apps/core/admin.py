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
    list_display = ("usuario", "vinculo", "status", "revisado_por", "revisado_em", "criado_em")
    list_filter = ("status",)
    search_fields = (
        "usuario__username",
        "usuario__email",
        "usuario__nome_exibicao",
        "usuario__vinculo_institucional",
        "justificativa",
    )
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("usuario", "revisado_por")
    actions = ["aprovar_solicitacoes", "rejeitar_solicitacoes"]

    @admin.display(description="Vínculo institucional", ordering="usuario__vinculo_institucional")
    def vinculo(self, obj: SolicitacaoCadastro) -> str:
        return obj.usuario.vinculo_institucional or "—"

    def _marcar_status(self, request, queryset, novo_status: str) -> int:
        from django.utils import timezone

        atualizadas = 0
        for s in queryset.filter(status=SolicitacaoCadastro.Status.PENDENTE):
            s.status = novo_status
            s.revisado_por = request.user
            s.revisado_em = timezone.now()
            s.save()  # dispara signal: promocao + e-mail
            atualizadas += 1
        return atualizadas

    @admin.action(description="Aprovar solicitações selecionadas (promove usuário)")
    def aprovar_solicitacoes(self, request, queryset):
        n = self._marcar_status(request, queryset, SolicitacaoCadastro.Status.APROVADA)
        self.message_user(request, f"{n} solicitação(ões) aprovada(s).")

    @admin.action(description="Rejeitar solicitações selecionadas")
    def rejeitar_solicitacoes(self, request, queryset):
        n = self._marcar_status(request, queryset, SolicitacaoCadastro.Status.REJEITADA)
        self.message_user(request, f"{n} solicitação(ões) rejeitada(s).")
