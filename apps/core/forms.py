"""Forms do app core."""

from __future__ import annotations

from django import forms

from .models import SolicitacaoCadastro


class SolicitacaoCadastroForm(forms.ModelForm):
    """
    Formulario de solicitacao de promocao a analista.

    Atualiza tambem o User vinculado com vinculo_institucional/grupo_pesquisa
    e nome_exibicao caso ainda nao estejam preenchidos.
    """

    nome_exibicao = forms.CharField(
        max_length=200,
        required=True,
        label="Nome de exibição",
        help_text="Como você quer ser identificado no acervo público.",
    )
    vinculo_institucional = forms.CharField(
        max_length=300,
        required=True,
        label="Vínculo institucional",
        help_text="Universidade, instituto ou grupo ao qual está vinculado.",
    )
    grupo_pesquisa = forms.CharField(
        max_length=300,
        required=False,
        label="Grupo de pesquisa",
    )
    orcid = forms.CharField(
        max_length=19,
        required=False,
        label="ORCID",
        help_text="Formato 0000-0000-0000-0000.",
    )

    class Meta:
        model = SolicitacaoCadastro
        fields = ["justificativa"]
        labels = {"justificativa": "Justificativa"}
        help_texts = {
            "justificativa": (
                "Descreva brevemente sua área de pesquisa e o motivo do "
                "interesse em participar do acervo."
            ),
        }
        widgets = {
            "justificativa": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario:
            self.fields["nome_exibicao"].initial = usuario.nome_exibicao or ""
            self.fields["vinculo_institucional"].initial = usuario.vinculo_institucional or ""
            self.fields["grupo_pesquisa"].initial = usuario.grupo_pesquisa or ""
            self.fields["orcid"].initial = usuario.orcid or ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.usuario:
            instance.usuario = self.usuario
            # Atualiza dados do User a partir do form
            self.usuario.nome_exibicao = self.cleaned_data["nome_exibicao"]
            self.usuario.vinculo_institucional = self.cleaned_data["vinculo_institucional"]
            self.usuario.grupo_pesquisa = self.cleaned_data.get("grupo_pesquisa", "")
            self.usuario.orcid = self.cleaned_data.get("orcid", "")
        if commit:
            if self.usuario:
                self.usuario.save()
            instance.save()
        return instance
