"""Formulários da triagem."""

from __future__ import annotations

from django import forms

from apps.vocabulario.models import TermoVocabulario

from .models import RegistroTriagem

# Os inputs são estilizados pelo design system via `.tg-field` nos templates
# (ver templates/triagem/_estilos.html); não injetamos classes utilitárias aqui.
_CSS = ""


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
    n_identificados = forms.IntegerField(
        required=True, min_value=0,
        label="Nº de registros que a base reportou",
        help_text=(
            "Total que a busca retornou na base (ex.: 466 no WoS). O sistema "
            "compara com o que vier no arquivo e avisa se houver divergência."
        ),
    )
    string_busca = forms.CharField(
        required=False, label="String de busca",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A query usada na base (para reprodutibilidade).",
    )
    filtros = forms.CharField(
        required=False, label="Filtros aplicados",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Ex.: anos 2017–2025; idioma inglês/português; tipo de documento: artigo.",
    )
    data_busca = forms.DateField(
        required=False, label="Data da busca",
        widget=forms.DateInput(attrs={"type": "date"}),
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # O __str__ de TermoVocabulario é "base:Nome"; no menu mostramos só o nome.
        self.fields["base_consulta"].label_from_instance = lambda obj: obj.nome
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
