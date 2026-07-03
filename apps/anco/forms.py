from django import forms

from apps.vocabulario.models import TermoVocabulario

from .models import ItemCorpus


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
        required=True,
        label="String de busca",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A query usada na base (registro/auditoria).",
    )
    data_busca = forms.DateField(
        required=True,
        label="Data da busca",
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
            ("medline", "PubMed (MEDLINE / .nbib)"),
        ],
    )
    arquivo = forms.FileField(label="Arquivo (RIS/BibTeX/CSV/PubMed)")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # O `__str__` do termo é "base:Scopus" (prefixo do vocabulário); no
        # formulário queremos só o nome legível da base.
        self.fields["base_consulta"].label_from_instance = lambda obj: obj.nome

    def clean(self):
        cd = super().clean()
        if not cd.get("base_consulta") and not (cd.get("outra_base") or "").strip():
            raise forms.ValidationError("Informe a base de consulta (do vocabulário ou outra).")
        return cd


class ItemCorpusForm(forms.ModelForm):
    """Edita os campos bibliográficos de um item do corpus ANCO.

    Port do `RegistroFonteForm` da triagem (mesmos campos/labels/widgets); o
    sync para o `Artigo` vinculado é feito por `importacao.sincronizar_artigo`.
    """

    class Meta:
        model = ItemCorpus
        fields = [
            "titulo",
            "autores",
            "ano",
            "titulo_periodico",
            "doi",
            "isbn",
            "idioma",
            "tipo",
            "palavras_chaves",
            "resumo",
            "link",
        ]
        labels = {
            "titulo": "Título",
            "autores": "Autores",
            "ano": "Ano",
            "titulo_periodico": "Periódico/Fonte",
            "doi": "DOI",
            "isbn": "ISBN/ISSN",
            "idioma": "Idioma",
            "tipo": "Tipo de documento",
            "palavras_chaves": "Palavras-chave",
            "resumo": "Resumo",
            "link": "Link de acesso",
        }
        widgets = {
            "titulo": forms.Textarea(attrs={"rows": 2}),
            "autores": forms.Textarea(attrs={"rows": 2}),
            "palavras_chaves": forms.Textarea(attrs={"rows": 2}),
            "resumo": forms.Textarea(attrs={"rows": 7}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "field-textarea"
            else:
                field.widget.attrs["class"] = "field-input"
