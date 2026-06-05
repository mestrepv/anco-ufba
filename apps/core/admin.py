"""Admin do app core."""

from allauth.account.admin import EmailAddressAdmin as AllauthEmailAddressAdmin
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .models import SolicitacaoCadastro, User

# Restaura a ação `delete_selected` no admin de EmailAddress do allauth.
# O allauth sobrescreve `actions = ['make_verified']`, removendo a delete
# padrão e impedindo apagar registros pela UI.
admin.site.unregister(EmailAddress)


@admin.register(EmailAddress)
class EmailAddressAdmin(AllauthEmailAddressAdmin, UnfoldModelAdmin):
    actions = ["make_verified", "delete_selected"]


@admin.register(User)
class UserAdmin(DjangoUserAdmin, UnfoldModelAdmin):
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

    actions = [
        "promover_curador",
        "promover_analista",
        "rebaixar_leitor",
        "aprovar_revisor",
        "conceder_admin",
        "revogar_admin",
    ]

    @admin.action(description="Promover papel a CURADOR")
    def promover_curador(self, request, queryset):
        n = queryset.update(papel=User.Papel.CURADOR)
        self.message_user(request, f"{n} usuário(s) promovido(s) a curador.")

    @admin.action(description="Definir papel como ANALISTA")
    def promover_analista(self, request, queryset):
        n = queryset.update(papel=User.Papel.ANALISTA)
        self.message_user(request, f"{n} usuário(s) definido(s) como analista.")

    @admin.action(description="Rebaixar papel para LEITOR")
    def rebaixar_leitor(self, request, queryset):
        n = queryset.update(papel=User.Papel.LEITOR)
        self.message_user(request, f"{n} usuário(s) rebaixado(s) a leitor.")

    @admin.action(description="Aprovar como revisor (entra no sorteio de triagem)")
    def aprovar_revisor(self, request, queryset):
        n = queryset.update(revisor_aprovado=True)
        self.message_user(request, f"{n} usuário(s) aprovado(s) como revisor.")

    @admin.action(description="Conceder acesso de admin do site (staff)")
    def conceder_admin(self, request, queryset):
        n = queryset.update(is_staff=True)
        self.message_user(
            request,
            f"{n} usuário(s) com acesso de admin. Para superusuário, marque na "
            "ficha do usuário.",
        )

    @admin.action(description="Revogar acesso de admin do site (staff)")
    def revogar_admin(self, request, queryset):
        # Nunca revoga o próprio acesso (evita travar a si mesmo).
        n = queryset.exclude(pk=request.user.pk).update(is_staff=False)
        self.message_user(request, f"{n} usuário(s) sem acesso de admin.")

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
class SolicitacaoCadastroAdmin(UnfoldModelAdmin):
    list_display = ("usuario", "tipo", "vinculo", "status", "revisado_por", "revisado_em", "criado_em")
    list_filter = ("tipo", "status")
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
