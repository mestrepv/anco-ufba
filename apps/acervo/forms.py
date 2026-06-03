"""Forms do app acervo: Artigo (lookup + metadados) e Analise multipasso."""

from __future__ import annotations

import re

from django import forms

from .models import Analise, Artigo, Resenha
from .services.crossref import normalizar_doi
from .services.isbn import validar_isbn

_CSS_INPUT = (
    "block w-full rounded-md border-slate-300 shadow-sm focus:border-anco focus:ring-anco text-sm"
)
_CSS_TEXTAREA = _CSS_INPUT + " min-h-[5rem]"
_DOI_CANONICO_RE = re.compile(r"^10\.\d{1,9}/\S+$")


def _classe_widget(field: forms.Field, css: str = _CSS_INPUT) -> None:
    """Adiciona classes Tailwind ao widget do campo."""
    existing = field.widget.attrs.get("class", "")
    field.widget.attrs["class"] = f"{existing} {css}".strip()


class IdentificadorLookupForm(forms.Form):
    """
    Form do passo 1 do cadastro de Artigo: campo único para o identificador.

    O `clean_identificador` detecta o tipo (doi/isbn/url/desconhecido) e
    devolve um dicionário `{tipo, valor}` já normalizado.
    """

    identificador = forms.CharField(
        max_length=200,
        required=False,
        label="DOI, ISBN ou URL do artigo",
        widget=forms.TextInput(
            attrs={
                "placeholder": "10.xxxx/yyy   ·   978...   ·   https://...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _classe_widget(self.fields["identificador"])

    def clean_identificador(self) -> dict:
        valor = (self.cleaned_data.get("identificador") or "").strip()
        if not valor:
            return {"tipo": "vazio", "valor": ""}

        doi = normalizar_doi(valor)
        if _DOI_CANONICO_RE.match(doi):
            return {"tipo": "doi", "valor": doi}

        isbn = validar_isbn(valor)
        if isbn:
            return {"tipo": "isbn", "valor": isbn}

        if valor.lower().startswith(("http://", "https://")):
            return {"tipo": "url", "valor": valor}

        return {"tipo": "desconhecido", "valor": valor}


class ArtigoMetadadosForm(forms.ModelForm):
    """
    Form de cadastro de Artigo com metadados editáveis.

    DOI e ISBN são opcionais individualmente; o `clean()` exige pelo menos
    um identificador (DOI, ISBN) OU os campos mínimos para gerar o
    `identificador_interno` automaticamente (título + ano).
    """

    class Meta:
        model = Artigo
        fields = [
            "doi",
            "isbn",
            "tipo_publicacao",
            "titulo",
            "titulo_periodico",
            "idioma",
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
        # Aplica classes do design system editorial (field-input / field-textarea)
        for _name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "field-textarea"
            else:
                field.widget.attrs["class"] = "field-input"
        # link_acesso continua obrigatório (acervo precisa do link)
        self.fields["link_acesso"].required = True
        self.fields["base_consulta"].required = True
        # Rótulo do dropdown = só o nome da base (sem o prefixo "base:" do
        # __str__, que existe para o admin distinguir os vocabulários).
        self.fields["base_consulta"].label_from_instance = lambda termo: termo.nome
        # Área (grande área CNPq/CAPES) é obrigatória no cadastro de artigos.
        self.fields["area"].required = True
        # DOI e ISBN ficam opcionais — clean() valida que pelo menos um existe
        self.fields["doi"].required = False
        self.fields["isbn"].required = False
        # tipo_publicacao tem default "artigo" no model; deixa não-obrigatório no form
        self.fields["tipo_publicacao"].required = False

    def clean_doi(self) -> str:
        doi = (self.cleaned_data.get("doi") or "").strip()
        if not doi:
            return ""
        doi_norm = normalizar_doi(doi)
        if not _DOI_CANONICO_RE.match(doi_norm):
            raise forms.ValidationError(
                "DOI deve seguir o formato 10.xxxx/yyy."
            )
        return doi_norm

    def clean_isbn(self) -> str:
        isbn = (self.cleaned_data.get("isbn") or "").strip()
        if not isbn:
            return ""
        validado = validar_isbn(isbn)
        if not validado:
            raise forms.ValidationError(
                "ISBN inválido — checksum não bate. Verifique se digitou todos os dígitos."
            )
        return validado

    def clean(self) -> dict:
        cleaned = super().clean()
        doi = cleaned.get("doi") or ""
        isbn = cleaned.get("isbn") or ""
        titulo = (cleaned.get("titulo") or "").strip()
        ano = cleaned.get("ano")
        if not doi and not isbn and not (titulo and ano):
            raise forms.ValidationError(
                "Informe DOI, ISBN, ou no mínimo título e ano para cadastrar o artigo."
            )
        return cleaned


# Alias temporário para preservar imports antigos (apps/acervo/views.py).
# Será removido quando o M5 reescrever a view.
ArtigoForm = ArtigoMetadadosForm


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
TODOS_OS_CAMPOS = CAMPOS_PRESENCA + CAMPOS_ESTRUTURA


class _AnaliseFormBase(forms.ModelForm):
    class Meta:
        model = Analise
        fields = ()  # subclasse define

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.SelectMultiple)):
                continue  # M2M e checkbox tem estilo proprio
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "field-textarea"
            else:
                field.widget.attrs["class"] = "field-input"
        # Rótulo dos termos de vocabulário = só o nome (sem o prefixo
        # "epistemologia:" / "teoria:" do __str__, que serve ao admin).
        for nome in ("epistemologia", "teoria"):
            if nome in self.fields:
                self.fields[nome].label_from_instance = lambda termo: termo.nome


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


class ResenhaForm(forms.ModelForm):
    """Form do texto da resenha crítica (entidade própria)."""

    class Meta:
        model = Resenha
        fields = ("texto",)
        widgets = {"texto": forms.Textarea(attrs={"rows": 12})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["texto"].required = True
        self.fields["texto"].label = "Resenha crítica"
        self.fields["texto"].widget.attrs["class"] = "field-textarea"


# Form completo (todos os campos editaveis) — usado pelo auto-save POST
class AnaliseCompletaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = TODOS_OS_CAMPOS


# ---------------------------------------------------------------------------
# Forms da revisao (Fase 4)
# ---------------------------------------------------------------------------


class RevisaoForm(forms.ModelForm):
    """Form do parecer e comentario geral. Campos ancorados sao gerenciados separadamente."""

    class Meta:
        from .models import Revisao

        model = Revisao
        fields = ("parecer", "comentario_geral")
        widgets = {
            "comentario_geral": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parecer"].required = True
        for _name, field in self.fields.items():
            css = _CSS_TEXTAREA if isinstance(field.widget, forms.Textarea) else _CSS_INPUT
            _classe_widget(field, css)


class ComentarioCampoForm(forms.Form):
    """Comentario ancorado a um campo especifico da analise."""

    campo = forms.CharField(max_length=50, widget=forms.HiddenInput)
    texto = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": "Comentário sobre este campo (opcional)"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _classe_widget(self.fields["texto"], _CSS_TEXTAREA)
