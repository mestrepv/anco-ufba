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
    "pt": "pt",
    "por": "pt",
    "português": "pt",
    "portugues": "pt",
    "pt-br": "pt",
    "en": "en",
    "eng": "en",
    "english": "en",
    "inglês": "en",
    "ingles": "en",
    "es": "es",
    "spa": "es",
    "español": "es",
    "espanhol": "es",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "français": "fr",
    "frances": "fr",
    "de": "de",
    "ger": "de",
    "deu": "de",
    "alemão": "de",
    "alemao": "de",
    "it": "it",
    "ita": "it",
    "italiano": "it",
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
        registro.doi,
        registro.isbn,
        registro.titulo,
        registro.ano,
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


def registrar_artigo_no_corpus(projeto, artigo, por):
    """Põe um `Artigo` avulso (cadastrado por "Artigo individual") no corpus de um
    projeto: cria/garante um `RegistroTriagem` INCLUIDO apontando para o artigo,
    com proveniência numa `Busca` "Artigos individuais" do usuário. Idempotente.

    Legado é isento (já está no acervo curado): retorna None.
    """
    from django.utils import timezone

    from .models import Busca, RegistroTriagem, chave_dedup

    if getattr(artigo, "eh_legado", False):
        return None

    ident = chave_dedup(
        artigo.doi or "", artigo.isbn or "", artigo.titulo, artigo.ano, artigo.titulo_periodico
    )
    reg, _criado = RegistroTriagem.objects.get_or_create(
        protocolo=projeto,
        identificador=ident,
        defaults={
            "titulo": artigo.titulo,
            "autores": artigo.autores,
            "ano": artigo.ano,
            "doi": artigo.doi or "",
            "isbn": artigo.isbn or "",
            "resumo": artigo.resumo,
            "palavras_chaves": artigo.palavras_chaves,
            "titulo_periodico": artigo.titulo_periodico,
            "idioma": artigo.idioma or "",
            "status": RegistroTriagem.Status.INCLUIDO,
            "artigo": artigo,
            "decisao_final": RegistroTriagem.Decisao.INCLUIR,
            "decidida_em": timezone.now(),
        },
    )
    # Já existia (ex.: importado antes): garante vínculo ao artigo e inclusão.
    campos = []
    if reg.artigo_id is None:
        reg.artigo = artigo
        campos.append("artigo")
    if reg.status != RegistroTriagem.Status.INCLUIDO and not reg.ja_no_acervo:
        reg.status = RegistroTriagem.Status.INCLUIDO
        reg.decisao_final = RegistroTriagem.Decisao.INCLUIR
        reg.decidida_em = timezone.now()
        campos += ["status", "decisao_final", "decidida_em"]
    if campos:
        reg.save(update_fields=campos)

    busca, _ = Busca.objects.get_or_create(
        protocolo=projeto, criado_por=por, outra_base="Artigos individuais"
    )
    ja_vinculado = busca.registros.filter(pk=reg.pk).exists()
    reg.origem_buscas.add(busca)
    if not ja_vinculado:
        # Mantém os contadores da "Busca" sintética coerentes (1 por artigo novo).
        from django.db.models import F

        Busca.objects.filter(pk=busca.pk).update(
            n_lidos=F("n_lidos") + 1,
            n_novos=F("n_novos") + 1,
            importado_em=timezone.now(),
        )
    return reg
