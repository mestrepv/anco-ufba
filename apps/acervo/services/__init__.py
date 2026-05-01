"""Serviços do app acervo: link, snapshot Wayback, lookup de DOI e ISBN."""

from ._base import LookupResultado
from .crossref import lookup_doi, normalizar_doi
from .isbn import lookup_isbn, validar_isbn
from .links import (
    LinkCheckResultado,
    aplicar_resultado_no_artigo,
    capturar_snapshot_wayback,
    validar_link,
)

__all__ = [
    "LinkCheckResultado",
    "LookupResultado",
    "aplicar_resultado_no_artigo",
    "capturar_snapshot_wayback",
    "lookup_doi",
    "lookup_isbn",
    "normalizar_doi",
    "validar_isbn",
    "validar_link",
]
