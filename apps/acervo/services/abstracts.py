"""Recuperação do melhor *abstract* possível para um DOI.

Consolida a cascata Crossref → OpenAlex usada pelos comandos de backfill de
resumo (corpus ANCO e acervo). A Crossref traz o metadado oficial; a OpenAlex
cobre mais casos de abstract. Devolve-se o mais longo entre os dois, ignorando
versões truncadas (snippets terminados em reticências).
"""

from __future__ import annotations

from .crossref import lookup_doi
from .openalex import abstract_por_doi

_SUFIXOS_TRUNCADO = ("...", "…")


def esta_truncado(resumo: str) -> bool:
    """True se o texto parece um *snippet* cortado (termina em reticências)."""
    return (resumo or "").rstrip().endswith(_SUFIXOS_TRUNCADO)


def melhor_abstract(doi: str) -> tuple[str, str]:
    """Abstract mais completo para um DOI e a fonte ('crossref'/'openalex'/'').

    Tenta Crossref primeiro; se vier vazio ou truncado, tenta OpenAlex. Entre os
    candidatos íntegros (não truncados), devolve o mais longo.
    """
    candidatos: list[tuple[str, str]] = []
    res = lookup_doi(doi)
    if res.encontrado:
        ab = (res.dados.get("resumo") or "").strip()
        if ab and not esta_truncado(ab):
            candidatos.append((ab, "crossref"))
    ab_oa = abstract_por_doi(doi).strip()
    if ab_oa and not esta_truncado(ab_oa):
        candidatos.append((ab_oa, "openalex"))
    if not candidatos:
        return "", ""
    return max(candidatos, key=lambda c: len(c[0]))
