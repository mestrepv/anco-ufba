"""Importação ANCO: lista bibliográfica → **corpus** (sem triagem).

Diferente do PRISMA: todo registro novo entra direto no corpus e é
promovido/vinculado a um `acervo.Artigo` na hora. Dedup interno por
`identificador` (mesma referência entre fontes só funde a origem). O acervo
curado nunca é alterado — `_promover` **reusa** o Artigo existente quando casa.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.acervo.models import Artigo, _gerar_identificador_interno

from .dedup import chave_dedup, normalizar_doi
from .models import FonteImport, ItemCorpus

logger = logging.getLogger(__name__)

# Idiomas livres → choices de Artigo.Idioma (cópia própria).
_IDIOMAS = {
    "pt": "pt", "por": "pt", "português": "pt", "portugues": "pt", "pt-br": "pt",
    "en": "en", "eng": "en", "english": "en", "inglês": "en", "ingles": "en",
    "es": "es", "spa": "es", "español": "es", "espanhol": "es",
    "fr": "fr", "fra": "fr", "fre": "fr", "français": "fr", "frances": "fr",
    "de": "de", "ger": "de", "deu": "de", "alemão": "de", "alemao": "de",
    "it": "it", "ita": "it", "italiano": "it",
}


def _idioma(valor: str) -> str:
    return _IDIOMAS.get((valor or "").strip().lower(), "")


def _artigo_no_acervo(doi: str, isbn: str, titulo: str, ano: int | None, periodico: str):
    """Retorna o `Artigo` existente correspondente, ou None (inclui o legado)."""
    if doi:
        a = Artigo.objects.filter(doi__iexact=doi).first()
        if a:
            return a
    if isbn:
        isbn_n = isbn.replace("-", "").replace(" ", "")
        a = Artigo.objects.filter(isbn__in=[isbn, isbn_n]).first()
        if a:
            return a
    ident = _gerar_identificador_interno(titulo, ano, periodico)
    return Artigo.objects.filter(identificador_interno=ident).first()


def _base_consulta(item: ItemCorpus):
    f = item.origem_fontes.filter(base_consulta__isnull=False).first()
    return f.base_consulta if f else None


def promover(item: ItemCorpus) -> Artigo:
    """Vincula o item a um `Artigo` do acervo (reusa se existir; nunca altera o curado)."""
    if item.artigo_id:
        return item.artigo
    artigo = _artigo_no_acervo(item.doi, item.isbn, item.titulo, item.ano, item.titulo_periodico)
    if artigo is None:
        artigo = Artigo(
            doi=item.doi or None,
            isbn=item.isbn or None,
            titulo=item.titulo,
            autores=item.autores,
            ano=item.ano,
            resumo=item.resumo,
            palavras_chaves=item.palavras_chaves,
            titulo_periodico=item.titulo_periodico,
            idioma=_idioma(item.idioma),
            link_acesso=item.link or "",
            base_consulta=_base_consulta(item),
            eh_legado=False,
        )
        artigo.save()  # gera identificador_interno quando não há DOI/ISBN
        logger.info("Item ANCO %s promovido ao Artigo %s", item.pk, artigo.pk)
    item.artigo = artigo
    item.save(update_fields=["artigo"])
    return artigo


@dataclass
class ResultadoImport:
    total: int = 0
    novos: int = 0
    duplicados: int = 0
    ignorados: int = 0


@transaction.atomic
def importar_para_fonte(fonte: FonteImport, registros_brutos: list[dict]) -> ResultadoImport:
    """Cria `ItemCorpus` para cada referência nova e promove ao acervo."""
    projeto = fonte.projeto
    res = ResultadoImport()

    for bruto in registros_brutos:
        res.total += 1
        titulo = (bruto.get("titulo") or "").strip()
        if not titulo:
            res.ignorados += 1
            continue

        doi = normalizar_doi(bruto.get("doi") or "")
        isbn = (bruto.get("isbn") or "").strip()
        ano = bruto.get("ano")
        periodico = (bruto.get("titulo_periodico") or "").strip()
        ident = chave_dedup(doi, isbn, titulo, ano, periodico)

        existente = ItemCorpus.objects.filter(projeto=projeto, identificador=ident).first()
        if existente is not None:
            existente.origem_fontes.add(fonte)
            res.duplicados += 1
            continue

        item = ItemCorpus(
            projeto=projeto,
            titulo=titulo,
            autores=(bruto.get("autores") or "").strip(),
            ano=ano,
            doi=doi,
            isbn=isbn,
            resumo=(bruto.get("resumo") or "").strip(),
            palavras_chaves=(bruto.get("palavras_chaves") or "").strip(),
            titulo_periodico=periodico,
            idioma=(bruto.get("idioma") or "").strip()[:20],
            link=(bruto.get("link") or "").strip()[:600],
            tipo=(bruto.get("tipo") or "").strip()[:40],
            identificador=ident,
        )
        item.save()
        item.origem_fontes.add(fonte)
        promover(item)  # ANCO: tudo entra no corpus E já vira/aponta Artigo
        res.novos += 1

    fonte.n_lidos = res.total
    fonte.n_novos = res.novos
    fonte.n_duplicados = res.duplicados
    fonte.n_ignorados = res.ignorados
    fonte.importado_em = timezone.now()
    fonte.save(
        update_fields=["n_lidos", "n_novos", "n_duplicados", "n_ignorados", "importado_em"]
    )
    logger.info(
        "Import ANCO fonte=%s base=%s total=%d novos=%d dup=%d ign=%d",
        fonte.pk,
        fonte.base_nome,
        res.total,
        res.novos,
        res.duplicados,
        res.ignorados,
    )
    return res
