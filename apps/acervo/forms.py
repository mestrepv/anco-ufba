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
            "area_outra",
            "autores",
            "vinculacao_institucional",
            "palavras_chaves",
            "resumo",
            "base_consulta",
            "link_acesso",
            "link_acesso_alternativo",
            "artigo_pago",
            "acesso_aberto",
            "pago_sem_capes",
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
        # Completude para a análise: resumo, autores e palavras-chave passam a ser
        # obrigatórios (o sorteio "só completos" depende deles).
        for _obrig in ("resumo", "autores", "palavras_chaves"):
            self.fields[_obrig].required = True
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
            raise forms.ValidationError("DOI deve seguir o formato 10.xxxx/yyy.")
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
        if (
            cleaned.get("area") == Artigo.Area.OUTROS
            and not (cleaned.get("area_outra") or "").strip()
        ):
            self.add_error("area_outra", "Especifique a área quando escolher 'Outros'.")
        return cleaned


# Alias temporário para preservar imports antigos (apps/acervo/views.py).
# Será removido quando o M5 reescrever a view.
ArtigoForm = ArtigoMetadadosForm


class ArtigoAreaForm(forms.ModelForm):
    """Edição da área de conhecimento do artigo (passo Identificação da análise)."""

    class Meta:
        model = Artigo
        fields = ("area", "area_outra")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].required = True
        self.fields["area"].label = "Área de conhecimento"
        self.fields["area"].widget.attrs["class"] = "field-input"
        self.fields["area_outra"].required = False
        self.fields["area_outra"].label = "Especifique a área"
        self.fields["area_outra"].widget.attrs["class"] = "field-input"

    def clean(self):
        dados = super().clean()
        if dados.get("area") == Artigo.Area.OUTROS and not (dados.get("area_outra") or "").strip():
            self.add_error("area_outra", "Especifique a área quando escolher 'Outros'.")
        return dados


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

# Booleanos de presença/pertinência: Sim/Não (radio), sem "Desconhecido".
CAMPOS_SIM_NAO = (
    "presenca_titulo",
    "presenca_resumo",
    "presenca_palavras_chave",
    "presenca_referencias",
    "presenca_corpo",
    "pertinencia",
    "define_conceito",
)


class _AnaliseFormBase(forms.ModelForm):
    class Meta:
        model = Analise
        fields = ()  # subclasse define

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Booleanos como Sim/Não (radio) — sem dropdown nem "Desconhecido".
        # O campo continua opcional (não respondido = em branco); a trava de
        # completude exige resposta na submissão.
        for nome in CAMPOS_SIM_NAO:
            if nome in self.fields:
                self.fields[nome].widget = forms.RadioSelect(
                    choices=[(True, "Sim"), (False, "Não")]
                )
        for _name, field in self.fields.items():
            if isinstance(
                field.widget,
                (forms.CheckboxInput, forms.SelectMultiple, forms.RadioSelect),
            ):
                continue  # M2M, checkbox e radio têm estilo próprio
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "field-textarea"
            else:
                field.widget.attrs["class"] = "field-input"
        # Rótulo dos termos de vocabulário = só o nome (sem o prefixo
        # "epistemologia:" / "teoria:" do __str__, que serve ao admin).
        # Picker só oferece termos ATIVOS (a curadoria desativa compostos/lixo),
        # mas SEMPRE inclui os já selecionados nesta análise — para não perder
        # valores antigos (ex.: rascunho que referencia um termo já desativado).
        from django.db.models import Q

        for nome in ("epistemologia", "teoria"):
            if nome not in self.fields:
                continue
            self.fields[nome].label_from_instance = lambda termo: termo.nome
            qs = self.fields[nome].queryset
            selecionados = (
                self.instance.pk
                and list(getattr(self.instance, nome).values_list("pk", flat=True))
                or []
            )
            self.fields[nome].queryset = qs.filter(Q(ativo=True) | Q(pk__in=selecionados))


class AnalisePresencaForm(_AnaliseFormBase):
    class Meta(_AnaliseFormBase.Meta):
        fields = CAMPOS_PRESENCA
        widgets = {
            "aspectos_relevantes": forms.Textarea(attrs={"rows": 3}),
            "definicao_extraida": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "presenca_titulo": "Aparece no título?",
            "presenca_resumo": "Aparece no resumo?",
            "presenca_palavras_chave": "Aparece nas palavras-chave?",
            "presenca_referencias": "Aparece nas referências?",
            "presenca_corpo": "Aparece no corpo do texto?",
            "pertinencia": "A obra é pertinente à Análise Cognitiva?",
            "aspectos_relevantes": "Aspectos relevantes",
            "define_conceito": "A obra define o conceito de Análise Cognitiva?",
            "definicao_extraida": "Definição extraída",
        }
        help_texts = {
            "pertinencia": (
                "Responda SIM quando a obra trabalha com/sobre o conhecimento de modo "
                "que dialoga com a AnCo — mesmo que não use o termo. O campo é "
                "emergente: na dúvida, RECONHEÇA e justifique (em Aspectos relevantes) "
                "em vez de excluir pela área/disciplina."
            ),
            "aspectos_relevantes": (
                "Em QUE e COMO a obra dialoga com a Análise Cognitiva — que dimensões e "
                "processos do trabalho com o conhecimento ela mobiliza. É aqui que a "
                "decisão de pertinência se fundamenta."
            ),
            "define_conceito": (
                "Marque SIM só para uma definição genuína (a obra enuncia o que entende "
                "por AnCo), não para menção vaga/alusiva. A ausência de definição é dado "
                "descritivo de um campo emergente — registre, não penalize."
            ),
            "definicao_extraida": "Se a obra define o conceito, transcreva a definição tal como ela a enuncia.",
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
        labels = {
            "teoria": "Teoria de referência",
            "contexto_producao": "Contexto de produção (opcional)",
            "observacoes": "Observações (opcional)",
        }
        help_texts = {
            "objeto": "O que (ou quem) a obra investiga.",
            "objetivo": "O que a obra se propõe a alcançar.",
            "foco": (
                "Recorte ou ângulo central — o SUBCAMPO cognitivo da obra (ex.: "
                "Linguística Cognitiva, Neurociência Cognitiva, Engenharia Cognitiva). "
                "NÃO confunda com a grande área CAPES (aba 1)."
            ),
            "metodologia": "Métodos e procedimentos de pesquisa.",
            "epistemologia": (
                "Posições epistemológicas — digite para buscar e selecione termos do "
                "vocabulário. Use os termos existentes para que as análises sejam "
                "agregáveis; glosas longas vão em Observações."
            ),
            "teoria": "Teorias mobilizadas — digite para buscar e selecione termos do vocabulário.",
            "referenciais": "Principais autores e obras de referência.",
            "resultados": "Principais achados ou conclusões.",
            "contexto_producao": "Onde/como a obra foi produzida (país, área, projeto). Opcional.",
            "observacoes": "Anotações livres do analista. Opcional.",
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
