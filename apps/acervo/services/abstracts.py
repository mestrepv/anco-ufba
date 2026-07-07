"""Recuperação do melhor *abstract* possível para um DOI.

Consolida a cascata Crossref → OpenAlex usada pelos comandos de backfill de
resumo (corpus ANCO e acervo). A Crossref traz o metadado oficial; a OpenAlex
cobre mais casos de abstract. Devolve-se o mais longo entre os dois, ignorando
versões truncadas (snippets terminados em reticências).
"""

from __future__ import annotations

from .crossref import lookup_doi
from .openalex import abstract_por_doi, keywords_por_doi

_SUFIXOS_TRUNCADO = ("...", "…")

# Rótulo de procedência das keywords recuperadas (não são do autor).
FONTE_LABEL = {"crossref": "Crossref", "openalex": "OpenAlex"}


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


def melhor_keywords(doi: str) -> tuple[list[str], str]:
    """Palavras-chave para um DOI e a fonte ('crossref'/'openalex'/'').

    Prefere os *subjects* da Crossref (fornecidos pelo editor); na ausência, cai
    para as keywords algorítmicas da OpenAlex. Ambas são não-autorais — o chamador
    deve sinalizar a procedência ao gravar.
    """
    res = lookup_doi(doi)
    if res.encontrado:
        subs = [s.strip() for s in (res.dados.get("palavras_chave") or []) if s and s.strip()]
        if subs:
            return subs, "crossref"
    kws = keywords_por_doi(doi)
    if kws:
        return kws, "openalex"
    return [], ""
