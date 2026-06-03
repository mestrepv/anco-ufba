"""
JSON-LD (schema.org) para paginas publicas (Fase 6).

Permite que Google Scholar, Zotero e agregadores academicos descubram
metadados estruturados das paginas sem precisar de API REST dedicada.
"""

from __future__ import annotations

import json

from django.conf import settings


def _base_url() -> str:
    return getattr(settings, "BASE_URL", "https://anco.local").rstrip("/")


def schema_artigo(artigo) -> dict:
    """
    schema.org/ScholarlyArticle para a pagina /artigo/<slug>/.

    Identifica o artigo cientifico em si (a obra externa), nao a analise
    feita sobre ele. Use isso para que motores de busca entendam o que
    a pagina descreve.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "name": artigo.titulo,
        "headline": artigo.titulo,
    }
    if artigo.doi and not artigo.doi.startswith("legacy:"):
        data["sameAs"] = f"https://doi.org/{artigo.doi}"
        data["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": artigo.doi}
    if artigo.ano:
        data["datePublished"] = str(artigo.ano)
    if artigo.titulo_periodico:
        data["isPartOf"] = {
            "@type": "Periodical",
            "name": artigo.titulo_periodico,
        }
    if artigo.autores:
        data["author"] = [
            {"@type": "Person", "name": a.strip()}
            for a in artigo.autores.replace(";", ",").split(",")
            if a.strip()
        ][:20]  # limite para nao explodir
    if artigo.resumo:
        data["abstract"] = artigo.resumo[:5000]
    if artigo.link_acesso:
        data["url"] = artigo.link_acesso
    if artigo.acesso_aberto:
        data["isAccessibleForFree"] = True
    return data


def schema_analise(analise) -> dict:
    """
    schema.org/Review para a pagina /analise/<id>/.

    A AnCo "review" um artigo. Tipo Review combina com metadados de
    autor (analista), criado_em, e a obra revisada (itemReviewed).
    """
    base = _base_url()
    autor = analise.analista
    autor_nome = autor.nome_exibicao or autor.get_full_name() or autor.username

    data = {
        "@context": "https://schema.org",
        "@type": "Review",
        "@id": f"{base}/analise/{analise.pk}/",
        "url": f"{base}/analise/{analise.pk}/",
        "name": f"Análise cognitiva: {analise.artigo.titulo}",
        "author": {"@type": "Person", "name": autor_nome},
        "datePublished": ((analise.publicada_em or analise.criado_em).date().isoformat()),
        "itemReviewed": schema_artigo(analise.artigo),
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "publisher": {"@type": "Organization", "name": "AnCo · Plataforma de Análise Cognitiva"},
    }
    resenha = getattr(analise, "resenha", None)
    if resenha and resenha.status in ("publicada", "legado"):
        data["reviewBody"] = resenha.texto[:5000]
    return data


def jsonld(data: dict) -> str:
    """Serializa para string segura para `<script type="application/ld+json">`."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
