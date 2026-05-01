"""
Lookup de metadados de artigo via Crossref.

Uma única API: https://api.crossref.org/works/<doi>. Cobertura típica
de ~95% para metadados estruturais (título, autores, periódico, ano,
páginas, ISSN, citações). Abstract sai em ~30–50% dos casos — quando
o editor depositou. Quando não vier, o template de preview mostra o
campo vazio e o analista cola do PDF na hora da análise.

Sem cascata para Semantic Scholar / OpenAlex: a complexidade da
orquestração não compensa o ganho marginal de cobertura de abstract,
que é opcional.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

from ._base import LookupResultado

logger = logging.getLogger(__name__)

USER_AGENT = "AnCo/1.0 (mailto:paulovicente.ifba@gmail.com)"
CROSSREF_TIMEOUT_SEGUNDOS = 5
CACHE_TTL_SEGUNDOS = 24 * 3600  # 24h
CACHE_PREFIXO = "lookup:doi:"

_DOI_CANONICO_RE = re.compile(r"^10\.\d{1,9}/\S+$")
_DOI_PREFIXOS_URL = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.I)
_DOI_PREFIXO_TEXTO = re.compile(r"^doi[:\s]+", re.I)
_TAGS_JATS = re.compile(r"<[^>]+>")


def normalizar_doi(raw: str) -> str:
    """Strip de prefixos comuns (`https://doi.org/`, `doi:`, espaços)."""
    s = (raw or "").strip()
    s = _DOI_PREFIXOS_URL.sub("", s)
    s = _DOI_PREFIXO_TEXTO.sub("", s)
    return s.strip()


def _limpa_abstract(raw: str) -> str:
    """Remove tags JATS (<jats:p>, etc.) e normaliza espaços."""
    if not raw:
        return ""
    sem_tags = _TAGS_JATS.sub(" ", raw)
    return re.sub(r"\s+", " ", sem_tags).strip()


def _autores_str(autores: list[str]) -> str:
    """Formato compacto: 'Silva, J.; Souza, M.; et al.' quando >4 autores."""
    if len(autores) > 4:
        return "; ".join(autores[:3]) + "; et al."
    return "; ".join(autores)


def _tipo_legivel(tipo_crossref: str) -> str:
    mapa = {
        "journal-article": "Artigo de periódico",
        "book-chapter": "Capítulo de livro",
        "book": "Livro",
        "proceedings-article": "Artigo de evento",
        "dissertation": "Tese / dissertação",
        "report": "Relatório",
        "monograph": "Monografia",
        "reference-entry": "Verbete de referência",
        "edited-book": "Livro editado",
    }
    return mapa.get(tipo_crossref, tipo_crossref or "")


def _normaliza_dados(message: dict, doi: str) -> dict:
    """Converte resposta crua da Crossref no formato consumido pelo template."""
    autores = []
    for a in message.get("author") or []:
        nome = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
        if nome:
            autores.append(nome)

    parts = ((message.get("published") or message.get("published-print") or {}).get(
        "date-parts", [[]]
    ) or [[]])[0]
    ano = parts[0] if parts else ""

    issn_types = {
        i.get("type"): i.get("value") for i in message.get("issn-type") or []
    }
    licenca = ((message.get("license") or [{}])[0]).get("URL", "")

    return {
        "doi": message.get("DOI", doi),
        "titulo": (message.get("title") or [""])[0],
        "autores": autores,
        "autores_str": _autores_str(autores),
        "periodico": (message.get("container-title") or [""])[0],
        "editora": message.get("publisher", ""),
        "tipo": _tipo_legivel(message.get("type", "")),
        "ano": ano,
        "volume": message.get("volume", ""),
        "numero": message.get("issue", ""),
        "paginas": message.get("page", ""),
        "issn": message.get("ISSN", []),
        "issn_print": issn_types.get("print", ""),
        "issn_electronic": issn_types.get("electronic", ""),
        "resumo": _limpa_abstract(message.get("abstract", "")),
        "palavras_chave": list(message.get("subject") or []),
        "url": message.get("URL", f"https://doi.org/{doi}"),
        "licenca": licenca,
        "citacoes_crossref": message.get("is-referenced-by-count", 0),
    }


def lookup_doi(doi_raw: str) -> LookupResultado:
    """
    Consulta a Crossref para um DOI e retorna metadados normalizados.

    Cacheia o resultado em Redis por 24h para evitar repetir chamadas.
    Erros (timeout, 404, rede) viram LookupResultado.encontrado=False
    com mensagem em `erro`.
    """
    doi = normalizar_doi(doi_raw)
    if not doi:
        return LookupResultado(encontrado=False, erro="identificador vazio")
    if not _DOI_CANONICO_RE.match(doi):
        return LookupResultado(encontrado=False, erro="formato de DOI inválido")

    chave_cache = CACHE_PREFIXO + doi
    cacheado = cache.get(chave_cache)
    if cacheado is not None:
        return cacheado

    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=CROSSREF_TIMEOUT_SEGUNDOS) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            resultado = LookupResultado(encontrado=False, erro="DOI não encontrado")
        else:
            resultado = LookupResultado(encontrado=False, erro=f"HTTP {exc.code}")
        cache.set(chave_cache, resultado, CACHE_TTL_SEGUNDOS)
        return resultado
    except (TimeoutError, urllib.error.URLError) as exc:
        # Erros transientes não são cacheados
        return LookupResultado(encontrado=False, erro=f"timeout: {exc}")
    except (json.JSONDecodeError, ValueError) as exc:
        return LookupResultado(encontrado=False, erro=f"resposta inválida: {exc}")

    message = payload.get("message", {})
    dados = _normaliza_dados(message, doi)
    resultado = LookupResultado(encontrado=True, dados=dados)
    cache.set(chave_cache, resultado, CACHE_TTL_SEGUNDOS)
    return resultado
