"""Formulários da triagem."""

from __future__ import annotations

import datetime

from django import forms

from apps.acervo.models import Artigo
from apps.vocabulario.models import TermoVocabulario

from .models import Busca, RegistroTriagem

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
        required=False, min_value=0,
        label="Nº de registros que a base reportou (opcional)",
        help_text=(
            "Deixe em branco para usar a contagem do próprio arquivo. Preencha só "
            "se quiser conferir contra o total relatado pela base (ex.: 466 no WoS)."
        ),
    )
    string_busca = forms.CharField(
        required=False, label="String de busca",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A query usada na base (para reprodutibilidade).",
    )
    campos_busca = forms.MultipleChoiceField(
        required=False, label="Campo(s) de busca",
        choices=Busca.CampoBusca.choices, widget=forms.CheckboxSelectMultiple,
        help_text="Onde a query foi aplicada na base (pode marcar mais de um).",
    )
    ano_inicio = forms.IntegerField(
        required=False, min_value=1900, widget=forms.HiddenInput,
    )
    ano_fim = forms.IntegerField(
        required=False, min_value=1900, widget=forms.HiddenInput,
    )
    idiomas = forms.MultipleChoiceField(
        required=False, label="Idiomas filtrados",
        choices=Artigo.Idioma.choices, widget=forms.CheckboxSelectMultiple,
    )
    idioma_outro = forms.CharField(
        required=False, max_length=100, label="Especifique o outro idioma",
    )
    tipos_documento = forms.MultipleChoiceField(
        required=False, label="Tipos de documento filtrados",
        choices=Busca.TipoDocumento.choices, widget=forms.CheckboxSelectMultiple,
    )
    filtros = forms.CharField(
        required=False, label="Outros filtros",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Só o que não couber nos campos acima (ex.: área da base, acesso aberto).",
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
        ano_max = datetime.date.today().year + 1
        ai, af = dados.get("ano_inicio"), dados.get("ano_fim")
        for campo in ("ano_inicio", "ano_fim"):
            v = dados.get(campo)
            if v and v > ano_max:
                self.add_error(campo, f"Ano não pode ser maior que {ano_max}.")
        if ai and af and ai > af:
            self.add_error("ano_fim", "O ano final deve ser ≥ ao ano inicial.")
        if "outro" in (dados.get("idiomas") or []) and not (
            dados.get("idioma_outro") or ""
        ).strip():
            self.add_error("idioma_outro", "Especifique o outro idioma.")
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
