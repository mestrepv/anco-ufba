"""Forms do app acervo: Artigo e formulario multipasso da Analise."""

from __future__ import annotations

from django import forms

from .models import Analise, Artigo

_CSS_INPUT = (
    "block w-full rounded-md border-slate-300 shadow-sm focus:border-anco focus:ring-anco text-sm"
)
_CSS_TEXTAREA = _CSS_INPUT + " min-h-[5rem]"


def _classe_widget(field: forms.Field, css: str = _CSS_INPUT) -> None:
    """Adiciona classes Tailwind ao widget do campo."""
    existing = field.widget.attrs.get("class", "")
    field.widget.attrs["class"] = f"{existing} {css}".strip()


class BuscaArtigoForm(forms.Form):
    """Busca por DOI ou texto livre no titulo/resumo."""

    q = forms.CharField(
        max_length=300,
        required=False,
        label="DOI ou termo de busca",
        widget=forms.TextInput(
            attrs={
                "placeholder": "10.xxxx/yyy ou trecho do título",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _classe_widget(self.fields["q"])


class ArtigoForm(forms.ModelForm):
    """Cadastro de novo Artigo a partir do fluxo de criacao de analise."""

    class Meta:
        model = Artigo
        fields = [
            "doi",
            "titulo",
            "titulo_periodico",
            "ano",
            "volume",
            "numero",
            "pagina_inicial",
            "pagina_final",
            "area",
            "autores",
            "vinculacao_institucional",
            "palavras_chaves",
            "resumo",
            "base_consulta",
            "link_acesso",
            "link_acesso_alternativo",
            "artigo_pago",
            "acesso_aberto",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 4}),
            "palavras_chaves": forms.Textarea(attrs={"rows": 2}),
            "autores": forms.Textarea(attrs={"rows": 2}),
            "vinculacao_institucional": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            css = _CSS_TEXTAREA if isinstance(field.widget, forms.Textarea) else _CSS_INPUT
            _classe_widget(field, css)
        # link_acesso e' obrigatorio por spec na criacao via fluxo novo
        self.fields["link_acesso"].required = True
        self.fields["base_consulta"].required = True

    def clean_doi(self):
        doi = (self.cleaned_data.get("doi") or "").strip()
        if not doi:
            raise forms.ValidationError("DOI obrigatorio.")
        return doi


# ---------------------------------------------------------------------------
# Forms parciais para o multipasso da Analise (cada um cobre um passo).
# ---------------------------------------------------------------------------

CAMPOS_PRESENCA = (
    "presenca_titulo",
    "presenca_resumo",
    "presenca_palavras_chave",
    "presenca_referencias",
    "presenca_corpo",
    "pertinencia",
    "aspectos_relevantes",
    "define_conceito",
    "definicao_extraida",
)
CAMPOS_ESTRUTURA = (
    "objeto",
    "objetivo",
    "foco",
    "metodologia",
    "epistemologia",
    "teoria",
    "referenciais",
    "resultados",
    "contexto_producao",
    "observacoes",
)
CAMPOS_RESENHA = ("resenha_critica",)
TODOS_OS_CAMPOS = CAMPOS_PRESENCA + CAMPOS_ESTRUTURA + CAMPOS_RESENHA


class _AnaliseFormBase(forms.ModelForm):
    class Meta:
        model = Analise
        fields = ()  # subclasse define

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            css = _CSS_TEXTAREA if isinstance(field.widget, forms.Textarea) else _CSS_INPUT
            if isinstance(field.widget, (forms.CheckboxInput, forms.SelectMultiple)):
                continue  # M2M e checkbox tem estilo proprio
            _classe_widget(field, css)


class AnalisePresencaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = CAMPOS_PRESENCA
        widgets = {
            "aspectos_relevantes": forms.Textarea(attrs={"rows": 3}),
            "definicao_extraida": forms.Textarea(attrs={"rows": 3}),
        }


class AnaliseEstruturaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = CAMPOS_ESTRUTURA
        widgets = {
            "objeto": forms.Textarea(attrs={"rows": 2}),
            "objetivo": forms.Textarea(attrs={"rows": 2}),
            "foco": forms.Textarea(attrs={"rows": 2}),
            "metodologia": forms.Textarea(attrs={"rows": 3}),
            "referenciais": forms.Textarea(attrs={"rows": 3}),
            "resultados": forms.Textarea(attrs={"rows": 3}),
            "contexto_producao": forms.Textarea(attrs={"rows": 2}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }


class AnaliseResenhaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = CAMPOS_RESENHA
        widgets = {
            "resenha_critica": forms.Textarea(attrs={"rows": 12}),
        }


# Form completo (todos os campos editaveis) — usado pelo auto-save POST
class AnaliseCompletaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = TODOS_OS_CAMPOS
