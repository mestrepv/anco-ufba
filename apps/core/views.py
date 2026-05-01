"""Views do app core: home, solicitacao de promocao, status."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import SolicitacaoCadastroForm
from .models import SolicitacaoCadastro

_CROSSREF_UA = "AnCo/1.0 (mailto:paulovicente.ifba@gmail.com)"
_SEMANTIC_UA = "AnCo/1.0"


def _crossref(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": _CROSSREF_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("message", {})
    except urllib.error.HTTPError as e:
        return {"_erro": f"CrossRef: HTTP {e.code}"}
    except Exception as e:
        return {"_erro": str(e)}


def _semantic_scholar(doi: str) -> dict:
    fields = "title,abstract,year,authors,externalIds,openAccessPdf,fieldsOfStudy"
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='')}" \
          f"?fields={fields}"
    req = urllib.request.Request(url, headers={"User-Agent": _SEMANTIC_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError:
        return {}
    except Exception:
        return {}


def _extrair_dados(doi: str) -> dict:
    cr = _crossref(doi)
    ss = _semantic_scholar(doi)

    if "_erro" in cr:
        return {"erro": cr["_erro"], "doi": doi}

    def autores(items):
        out = []
        for a in items or []:
            nome = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
            afil = "; ".join(af.get("name", "") for af in a.get("affiliation", []))
            out.append({"nome": nome, "afiliacao": afil})
        return out

    def data_pub(cr_data):
        parts = (cr_data or {}).get("date-parts", [[]])[0]
        if not parts:
            return None
        return "-".join(str(p) for p in parts)

    resumo = cr.get("abstract") or ss.get("abstract") or ""
    # CrossRef retorna abstract com tags JATS — remove <jats:p> etc.
    import re
    resumo = re.sub(r"<[^>]+>", " ", resumo).strip()

    issns = cr.get("ISSN", [])
    issn_types = {i.get("type"): i.get("value") for i in cr.get("issn-type", [])}

    return {
        "doi": cr.get("DOI", doi),
        "titulo": (cr.get("title") or [""])[0],
        "autores": autores(cr.get("author")),
        "periodico": (cr.get("container-title") or [""])[0],
        "editora": cr.get("publisher", ""),
        "tipo": cr.get("type", ""),
        "ano": data_pub(cr.get("published")),
        "volume": cr.get("volume", ""),
        "numero": cr.get("issue", ""),
        "paginas": cr.get("page", ""),
        "issn": issns,
        "issn_print": issn_types.get("print", ""),
        "issn_electronic": issn_types.get("electronic", ""),
        "resumo": resumo,
        "palavras_chave": [s.get("name", "") for s in cr.get("subject", [])],
        "url": cr.get("URL", f"https://doi.org/{doi}"),
        "licenca": (cr.get("license") or [{}])[0].get("URL", ""),
        "referencias_count": cr.get("references-count", 0),
        "citacoes_crossref": cr.get("is-referenced-by-count", 0),
        "areas_ss": ss.get("fieldsOfStudy") or [],
        "pdf_aberto": (ss.get("openAccessPdf") or {}).get("url", ""),
        "erro": None,
    }


def consultar_doi_view(request: HttpRequest) -> HttpResponse:
    doi_raw = request.GET.get("doi", "").strip()
    dados = None
    if doi_raw:
        # Normaliza: remove prefixo URL e espaços
        import re
        doi_norm = re.sub(r"(?i)^(https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi_raw).strip()
        dados = _extrair_dados(doi_norm)
    return render(request, "ferramentas/consultar_doi.html", {"dados": dados, "doi_raw": doi_raw})


def home_view(request: HttpRequest) -> HttpResponse:
    """Pagina inicial publica. Aponta para login institucional ou para o acervo."""
    return render(request, "core/home.html")


def teste_design_view(request: HttpRequest) -> HttpResponse:
    """Página de teste do design system — remover antes de ir para produção."""
    colors = [
        ("paper", "#FBF9F4"), ("paper-2", "#F5F1E8"), ("paper-3", "#EDE7DA"),
        ("rule", "#E5DFCF"), ("rule-strong", "#D4CCB8"),
        ("ink", "#1A1816"), ("ink-2", "#3A352E"), ("ink-3", "#6B655B"), ("ink-4", "#948D80"),
        ("gold", "#B8862C"), ("gold-deep", "#8C6520"),
        ("review-bg", "#FBF7E8"), ("review-rule", "#E8DCA8"),
        ("danger", "#A03A2A"), ("ok", "#4A6B3A"), ("info", "#3A5A7A"),
    ]
    return render(request, "_teste_design.html", {"colors": colors})


@login_required
def solicitar_promocao_view(request: HttpRequest) -> HttpResponse:
    """
    Formulario de solicitacao de promocao a analista.

    Se ja existe solicitacao do usuario, redireciona para a tela de status.
    Se o usuario ja eh analista ou curador, redireciona para a home.
    """
    user = request.user
    if user.eh_analista:
        messages.info(request, "Você já é analista — não precisa solicitar promoção.")
        return redirect("home")

    existente = SolicitacaoCadastro.objects.filter(usuario=user).first()
    if existente:
        return redirect("promocao_status")

    if request.method == "POST":
        form = SolicitacaoCadastroForm(request.POST, usuario=user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Solicitação enviada. Você receberá um e-mail quando for analisada.",
            )
            return redirect("promocao_status")
    else:
        form = SolicitacaoCadastroForm(usuario=user)

    return render(request, "core/solicitar_promocao.html", {"form": form})


@login_required
def promocao_status_view(request: HttpRequest) -> HttpResponse:
    """Mostra o status da solicitacao do usuario logado."""
    solicitacao = SolicitacaoCadastro.objects.filter(usuario=request.user).first()
    return render(
        request,
        "core/promocao_status.html",
        {"solicitacao": solicitacao},
    )
