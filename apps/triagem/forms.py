"""Formulários da triagem."""

from __future__ import annotations

from django import forms

from apps.vocabulario.models import TermoVocabulario

from .models import RegistroTriagem

_CSS = (
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm "
    "focus:border-anco focus:ring-1 focus:ring-anco"
)


class ImportarBuscaForm(forms.Form):
    """Upload de um export (RIS/BibTeX/CSV) como uma `Busca` de uma base."""

    base_consulta = forms.ModelChoiceField(
        queryset=TermoVocabulario.objects.filter(
            vocabulario__codigo="base", ativo=True
        ).order_by("nome"),
        required=False,
        empty_label="— selecione a base —",
        label="Base de consulta",
    )
    outra_base = forms.CharField(
        required=False, label="Outra base (fora do vocabulário)", max_length=200
    )
    formato = forms.ChoiceField(
        required=False,
        label="Formato",
        choices=[
            ("", "Inferir pela extensão"),
            ("ris", "RIS"),
            ("bibtex", "BibTeX"),
            ("csv", "CSV"),
        ],
    )
    arquivo = forms.FileField(label="Arquivo exportado")
    string_busca = forms.CharField(
        required=False, label="String de busca", widget=forms.Textarea(attrs={"rows": 2})
    )
    n_identificados = forms.IntegerField(
        required=False, min_value=0, label="Nº identificados relatado pela base"
    )
    data_busca = forms.DateField(
        required=False, label="Data da busca",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            css = campo.widget.attrs.get("class", "")
            campo.widget.attrs["class"] = f"{css} {_CSS}".strip()

    def clean(self) -> dict:
        dados = super().clean()
        if not dados.get("base_consulta") and not (dados.get("outra_base") or "").strip():
            raise forms.ValidationError(
                "Informe a base de consulta (do vocabulário) ou 'Outra base'."
            )
        return dados


class DecisaoTriagemForm(forms.Form):
    """Parecer de triagem de um revisor (incluir/excluir/dúvida + motivo)."""

    decisao = forms.ChoiceField(
        choices=RegistroTriagem.Decisao.choices,
        widget=forms.RadioSelect,
        label="Sua decisão",
    )
    motivo_exclusao = forms.CharField(
        required=False, label="Motivo da exclusão",
        widget=forms.Textarea(attrs={"rows": 2, "class": _CSS}),
        help_text="Obrigatório se você excluir o registro.",
    )
    comentario = forms.CharField(
        required=False, label="Comentário (opcional)",
        widget=forms.Textarea(attrs={"rows": 2, "class": _CSS}),
    )

    def clean(self) -> dict:
        dados = super().clean()
        if dados.get("decisao") == RegistroTriagem.Decisao.EXCLUIR and not (
            dados.get("motivo_exclusao") or ""
        ).strip():
            self.add_error("motivo_exclusao", "Informe o motivo da exclusão.")
        return dados


class DesempateForm(forms.Form):
    """Decisão de desempate do curador para um registro divergente."""

    decisao = forms.ChoiceField(
        choices=[
            (RegistroTriagem.Decisao.INCLUIR, "Incluir"),
            (RegistroTriagem.Decisao.EXCLUIR, "Excluir"),
        ],
        widget=forms.RadioSelect,
        label="Decisão final",
    )
    motivo_exclusao = forms.CharField(
        required=False, label="Motivo da exclusão",
        widget=forms.Textarea(attrs={"rows": 2, "class": _CSS}),
    )

    def clean(self) -> dict:
        dados = super().clean()
        if dados.get("decisao") == RegistroTriagem.Decisao.EXCLUIR and not (
            dados.get("motivo_exclusao") or ""
        ).strip():
            self.add_error("motivo_exclusao", "Informe o motivo da exclusão.")
        return dados
