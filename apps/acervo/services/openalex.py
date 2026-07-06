"""
Lookup de **abstract** via OpenAlex — fallback da Crossref.

A Crossref só devolve abstract quando o editor o depositou (~30–50%). A
OpenAlex cobre bem mais casos, mas guarda o resumo como um *inverted index*
(`{palavra: [posições]}`) que precisa ser reconstruído. Este módulo expõe
uma única função — `abstract_por_doi` — usada pelo backfill de resumos do
corpus ANCO; não substitui a Crossref no fluxo de cadastro (que traz o
pacote completo de metadados).

API: https://api.openalex.org/works/https://doi.org/<doi>
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

from .crossref import normalizar_doi

logger = logging.getLogger(__name__)

USER_AGENT = "AnCo/1.0 (mailto:paulovicente.ifba@gmail.com)"
OPENALEX_TIMEOUT_SEGUNDOS = 8
CACHE_TTL_SEGUNDOS = 24 * 3600  # 24h
CACHE_PREFIXO = "openalex:abstract:"

_DOI_CANONICO_RE = re.compile(r"^10\.\d{1,9}/\S+$")


def _reconstruir_abstract(indice: dict) -> str:
    """Reconstrói o texto a partir do `abstract_inverted_index` da OpenAlex.

    `indice` mapeia cada palavra à lista de posições em que ocorre. Ordena
    todas as (posição, palavra) e junta na ordem do texto original.
    """
    if not indice:
        return ""
    posicoes: list[tuple[int, str]] = []
    for palavra, idxs in indice.items():
        for i in idxs:
            posicoes.append((i, palavra))
    posicoes.sort(key=lambda p: p[0])
    return re.sub(r"\s+", " ", " ".join(palavra for _, palavra in posicoes)).strip()


def abstract_por_doi(doi_raw: str) -> str:
    """Devolve o abstract (texto) da OpenAlex para um DOI, ou "" se não houver.

    Cacheia em Redis por 24h (inclusive o resultado vazio, para não repetir a
    chamada). Qualquer erro de rede/parse vira "" — é um fallback best-effort.
    """
    doi = normalizar_doi(doi_raw)
    if not doi or not _DOI_CANONICO_RE.match(doi):
        return ""

    chave_cache = CACHE_PREFIXO + doi
    cacheado = cache.get(chave_cache)
    if cacheado is not None:
        return cacheado

    url = "https://api.openalex.org/works/" + urllib.parse.quote(
        f"https://doi.org/{doi}", safe=""
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=OPENALEX_TIMEOUT_SEGUNDOS) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # 404 = obra não indexada; cacheia vazio. Outros erros não cacheiam.
        if exc.code == 404:
            cache.set(chave_cache, "", CACHE_TTL_SEGUNDOS)
        else:
            logger.warning("OpenAlex HTTP %s para DOI %s", exc.code, doi)
        return ""
    except (TimeoutError, urllib.error.URLError) as exc:
        logger.warning("OpenAlex indisponível para DOI %s: %s", doi, exc)
        return ""
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("OpenAlex resposta inválida para DOI %s: %s", doi, exc)
        return ""

    abstract = _reconstruir_abstract(payload.get("abstract_inverted_index") or {})
    cache.set(chave_cache, abstract, CACHE_TTL_SEGUNDOS)
    return abstract
