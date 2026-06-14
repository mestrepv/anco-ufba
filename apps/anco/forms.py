from django import forms

from apps.vocabulario.models import TermoVocabulario


class ImportarFonteForm(forms.Form):
    """Upload de um export (RIS/BibTeX/CSV) como uma `FonteImport` ANCO.

    Enxuto: o ANCO não exige os filtros de reprodutibilidade do PRISMA.
    """

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
    string_busca = forms.CharField(
        required=False,
        label="String de busca",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A query usada na base (registro/auditoria).",
    )
    data_busca = forms.DateField(
        required=False,
        label="Data da busca",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    formato = forms.ChoiceField(
        required=False,
        label="Formato",
        choices=[("", "Inferir pela extensão"), ("ris", "RIS"), ("bibtex", "BibTeX"), ("csv", "CSV")],
    )
    arquivo = forms.FileField(label="Arquivo (RIS/BibTeX/CSV)")

    def clean(self):
        cd = super().clean()
        if not cd.get("base_consulta") and not (cd.get("outra_base") or "").strip():
            raise forms.ValidationError("Informe a base de consulta (do vocabulário ou outra).")
        return cd
