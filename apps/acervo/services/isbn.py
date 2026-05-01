"""
Lookup de metadados de livros e capítulos via OpenLibrary.

Uma única API: https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>.
Cobertura é boa para livros acadêmicos em inglês e parte dos
brasileiros — o que não estiver no OpenLibrary (ISBN não encontrado)
resulta em `LookupResultado.encontrado=False` e o analista preenche
manualmente.

Sem fallback Google Books: simplicidade > cobertura marginal.
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
OPENLIBRARY_TIMEOUT_SEGUNDOS = 5
CACHE_TTL_SEGUNDOS = 30 * 24 * 3600  # 30 dias (livros mudam menos)
CACHE_PREFIXO = "lookup:isbn:"


# ---------------------------------------------------------------------------
# Validação de ISBN-10 / ISBN-13
# ---------------------------------------------------------------------------


def _strip_isbn(raw: str) -> str:
    """Remove hífens, espaços e caracteres não-alfanuméricos."""
    return re.sub(r"[^0-9Xx]", "", (raw or ""))


def _checksum_isbn10(digitos: str) -> bool:
    """Valida checksum ISBN-10 (módulo 11). Aceita 'X' como dígito 10."""
    if len(digitos) != 10:
        return False
    soma = 0
    for i, c in enumerate(digitos):
        if c.upper() == "X":
            valor = 10
        elif c.isdigit():
            valor = int(c)
        else:
            return False
        soma += valor * (10 - i)
    return soma % 11 == 0


def _checksum_isbn13(digitos: str) -> bool:
    """Valida checksum ISBN-13 (módulo 10 com pesos 1 e 3 alternados)."""
    if len(digitos) != 13 or not digitos.isdigit():
        return False
    soma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digitos))
    return soma % 10 == 0


def validar_isbn(raw: str) -> str | None:
    """
    Normaliza e valida um ISBN-10 ou ISBN-13.

    Retorna o ISBN só com dígitos (e 'X' final preservado em ISBN-10) se
    o checksum bater; caso contrário, None.
    """
    s = _strip_isbn(raw).upper()
    if len(s) == 10 and _checksum_isbn10(s):
        return s
    if len(s) == 13 and _checksum_isbn13(s):
        return s
    return None


# ---------------------------------------------------------------------------
# Lookup OpenLibrary
# ---------------------------------------------------------------------------


def _autores_str(autores: list[str]) -> str:
    if len(autores) > 4:
        return "; ".join(autores[:3]) + "; et al."
    return "; ".join(autores)


def _ano_de_publicacao(publish_date: str) -> int | str:
    """Extrai o ano (4 dígitos) de uma string como 'January 2017' ou '2017'."""
    if not publish_date:
        return ""
    m = re.search(r"\b(\d{4})\b", publish_date)
    return int(m.group(1)) if m else publish_date


def _normaliza_dados(book: dict, isbn: str) -> dict:
    """Converte resposta do OpenLibrary no formato consumido pelo template."""
    autores = [a.get("name", "") for a in book.get("authors") or [] if a.get("name")]

    publishers = book.get("publishers") or []
    editora = publishers[0].get("name", "") if publishers else ""

    subjects = [s.get("name", "") for s in book.get("subjects") or [] if s.get("name")]

    # Identifiers podem trazer ISBN-10 e ISBN-13 separados
    ids = book.get("identifiers") or {}
    isbn_10 = (ids.get("isbn_10") or [""])[0]
    isbn_13 = (ids.get("isbn_13") or [""])[0]

    cover = (book.get("cover") or {}).get("large") or (book.get("cover") or {}).get("medium", "")

    # OpenLibrary usa 'description' em alguns registros, 'notes' em outros;
    # ambos podem vir como dict {"value": "..."} ou string.
    def _texto(campo) -> str:
        if isinstance(campo, dict):
            return campo.get("value", "")
        return campo or ""

    resumo = _texto(book.get("description")) or _texto(book.get("notes"))

    return {
        "doi": "",  # livros via ISBN não têm DOI
        "titulo": book.get("title", ""),
        "autores": autores,
        "autores_str": _autores_str(autores),
        "periodico": "",  # n/a para livros
        "editora": editora,
        "tipo": "Livro",
        "ano": _ano_de_publicacao(book.get("publish_date", "")),
        "volume": "",
        "numero": "",
        "paginas": str(book.get("number_of_pages", "") or ""),
        "isbn": isbn,
        "isbn_10": isbn_10,
        "isbn_13": isbn_13,
        "issn": [],
        "issn_print": "",
        "issn_electronic": "",
        "resumo": resumo.strip(),
        "palavras_chave": subjects[:10],
        "url": book.get("url", f"https://openlibrary.org/isbn/{isbn}"),
        "licenca": "",
        "citacoes_crossref": 0,
        "cover": cover,
    }


def lookup_isbn(isbn_raw: str) -> LookupResultado:
    """
    Consulta a OpenLibrary para um ISBN e retorna metadados normalizados.

    Cacheia o resultado por 30 dias. Erros (timeout, rede, ISBN inválido)
    viram LookupResultado.encontrado=False.
    """
    isbn = validar_isbn(isbn_raw)
    if not isbn:
        return LookupResultado(encontrado=False, erro="ISBN inválido (checksum falhou)")

    chave_cache = CACHE_PREFIXO + isbn
    cacheado = cache.get(chave_cache)
    if cacheado is not None:
        return cacheado

    bibkey = f"ISBN:{isbn}"
    url = (
        "https://openlibrary.org/api/books"
        f"?bibkeys={urllib.parse.quote(bibkey)}&format=json&jscmd=data"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=OPENLIBRARY_TIMEOUT_SEGUNDOS) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        resultado = LookupResultado(encontrado=False, erro=f"HTTP {exc.code}")
        cache.set(chave_cache, resultado, CACHE_TTL_SEGUNDOS)
        return resultado
    except (TimeoutError, urllib.error.URLError) as exc:
        # Erros transientes não são cacheados
        return LookupResultado(encontrado=False, erro=f"timeout: {exc}")
    except (json.JSONDecodeError, ValueError) as exc:
        return LookupResultado(encontrado=False, erro=f"resposta inválida: {exc}")

    book = payload.get(bibkey)
    if not book:
        # OpenLibrary retorna {} quando não encontra — não é erro, só ausência
        resultado = LookupResultado(encontrado=False, erro="ISBN não encontrado")
        cache.set(chave_cache, resultado, CACHE_TTL_SEGUNDOS)
        return resultado

    dados = _normaliza_dados(book, isbn)
    resultado = LookupResultado(encontrado=True, dados=dados)
    cache.set(chave_cache, resultado, CACHE_TTL_SEGUNDOS)
    return resultado
