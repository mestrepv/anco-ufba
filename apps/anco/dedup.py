"""Deduplicação do módulo ANCO — chave determinística por referência.

**Cópia própria** (independência do `apps/triagem`). Reutiliza apenas utilitários
da camada compartilhada `apps/acervo` (normalização de DOI e identificador
interno) — não importa nada de `apps/triagem`.

> Encanamento duplicado: correções precisam ser aplicadas também no
> `apps/triagem/models.chave_dedup`.
"""

from __future__ import annotations

from apps.acervo.models import _gerar_identificador_interno
from apps.acervo.services.crossref import normalizar_doi

__all__ = ["chave_dedup", "normalizar_doi"]


def chave_dedup(
    doi: str | None, isbn: str | None, titulo: str, ano: int | None, periodico: str
) -> str:
    """Chave determinística de deduplicação: DOI > ISBN > hash(título|ano|periódico).

    Mesmos campos → mesma chave (idempotente). Usada como `identificador` único do
    item dentro do projeto ANCO.
    """
    doi_norm = (doi or "").strip().lower()
    if doi_norm:
        return f"doi:{doi_norm}"
    isbn_norm = (isbn or "").strip().replace("-", "").replace(" ", "")
    if isbn_norm:
        return f"isbn:{isbn_norm}"
    return _gerar_identificador_interno(titulo, ano, periodico)
