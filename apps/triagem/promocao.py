"""Promoção de registros INCLUÍDOS ao acervo (`Artigo`).

Só os incluídos viram `Artigo` (status diferente de legado; `eh_legado=False`),
ficando disponíveis para análise pela Matriz AnCo (fluxo de `Analise` já
existente). Idempotente: re-promover devolve o mesmo `Artigo` sem duplicar.

Garantia do legado: registros que casam com `Artigo` existente são `ja_no_acervo`
e nem chegam à triagem; ainda assim, por segurança, a promoção reusa o `Artigo`
existente em vez de criar/alterar — nunca toca o acervo legado.
"""

from __future__ import annotations

import logging

from apps.acervo.models import Artigo

from .importacao import _artigo_no_acervo
from .models import RegistroTriagem

logger = logging.getLogger(__name__)

# Mapa de idiomas livres → choices de Artigo.Idioma.
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


def _base_consulta(registro: RegistroTriagem):
    busca = registro.origem_buscas.filter(base_consulta__isnull=False).first()
    return busca.base_consulta if busca else None


def promover_para_acervo(registro: RegistroTriagem) -> Artigo | None:
    """Cria (ou reusa) o `Artigo` de um registro incluído. Idempotente."""
    if registro.status != RegistroTriagem.Status.INCLUIDO:
        return None
    if registro.artigo_id:
        return registro.artigo  # já promovido

    # Segurança: se casar com Artigo existente, reusa (não cria/altera).
    artigo = _artigo_no_acervo(
        registro.doi, registro.isbn, registro.titulo, registro.ano,
        registro.titulo_periodico,
    )
    if artigo is None:
        artigo = Artigo(
            doi=registro.doi or None,
            isbn=registro.isbn or None,
            titulo=registro.titulo,
            autores=registro.autores,
            ano=registro.ano,
            resumo=registro.resumo,
            palavras_chaves=registro.palavras_chaves,
            titulo_periodico=registro.titulo_periodico,
            idioma=_idioma(registro.idioma),
            link_acesso=registro.link or "",
            base_consulta=_base_consulta(registro),
            eh_legado=False,
        )
        artigo.save()  # gera identificador_interno quando não há DOI/ISBN
        logger.info("Registro %s promovido ao Artigo %s", registro.pk, artigo.pk)

    registro.artigo = artigo
    registro.save(update_fields=["artigo"])
    return artigo
