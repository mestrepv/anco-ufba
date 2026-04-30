"""Tasks django-q2 para geração de embeddings."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger("busca_semantica")


def _texto_artigo(artigo) -> str:  # type: ignore[no-untyped-def]
    partes = [artigo.titulo, artigo.resumo, artigo.palavras_chaves]
    return " ".join(p for p in partes if p and p.strip())


def _texto_analise(analise) -> str:  # type: ignore[no-untyped-def]
    campos = [
        analise.objeto,
        analise.objetivo,
        analise.foco,
        analise.metodologia,
        analise.resultados,
        analise.aspectos_relevantes,
        analise.definicao_extraida,
        analise.referenciais,
    ]
    return " ".join(c for c in campos if c and c.strip())


def task_embedding_artigo(artigo_id: int) -> None:
    from apps.acervo.models import Artigo
    from apps.busca_semantica.embeddings import embed_texts

    try:
        artigo = Artigo.objects.get(pk=artigo_id)
    except Artigo.DoesNotExist:
        return

    texto = _texto_artigo(artigo)
    if not texto.strip():
        return

    results = embed_texts([texto])
    vec = results[0]
    if vec is None:
        logger.warning("Embedding falhou para Artigo %d — será refeito depois.", artigo_id)
        return

    Artigo.objects.filter(pk=artigo_id).update(
        embedding=vec,
        embedding_atualizado_em=datetime.now(tz=UTC),
    )
    logger.info("Embedding gerado para Artigo %d.", artigo_id)


def task_embedding_analise(analise_id: int) -> None:
    from apps.acervo.models import Analise
    from apps.busca_semantica.embeddings import embed_texts

    try:
        analise = Analise.objects.get(pk=analise_id)
    except Analise.DoesNotExist:
        return

    textos = []
    texto_estrutural = _texto_analise(analise)
    textos.append(texto_estrutural if texto_estrutural.strip() else "")

    texto_resenha = analise.resenha_critica or ""
    textos.append(texto_resenha)

    results = embed_texts([t for t in textos if t])
    idx = 0
    updates: dict = {"embedding_atualizado_em": datetime.now(tz=UTC)}

    if texto_estrutural.strip():
        vec = results[idx] if idx < len(results) else None
        if vec is not None:
            updates["embedding"] = vec
        else:
            logger.warning("Embedding estrutural falhou para Analise %d.", analise_id)
        idx += 1

    if texto_resenha.strip():
        vec = results[idx] if idx < len(results) else None
        if vec is not None:
            updates["embedding_resenha"] = vec
        else:
            logger.warning("Embedding de resenha falhou para Analise %d.", analise_id)

    Analise.objects.filter(pk=analise_id).update(**updates)
    logger.info("Embedding gerado para Analise %d.", analise_id)
