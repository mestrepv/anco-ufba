"""Wrapper para o serviço HTTP de embeddings.

Retry com backoff exponencial, timeout configurável e cache simples
em memória (LRU) para queries repetidas na mesma sessão.
"""

from __future__ import annotations

import functools
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger("busca_semantica")

_EMBEDDINGS_URL = getattr(settings, "EMBEDDINGS_URL", "http://embeddings:8080")
_TIMEOUT = getattr(settings, "EMBEDDINGS_TIMEOUT", 30)
_MAX_RETRIES = getattr(settings, "EMBEDDINGS_MAX_RETRIES", 3)
_RETRY_DELAY = 1.0  # segundos; dobra a cada tentativa


def _post_with_retry(texts: list[str]) -> list[list[float]]:
    delay = _RETRY_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                f"{_EMBEDDINGS_URL}/embed",
                json={"texts": texts},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except Exception as exc:
            if attempt == _MAX_RETRIES - 1:
                raise
            logger.warning("Embeddings tentativa %d falhou: %s. Aguardando %.1fs…", attempt + 1, exc, delay)
            time.sleep(delay)
            delay *= 2
    return []  # nunca alcançado


@functools.lru_cache(maxsize=256)
def _embed_cached(text: str) -> tuple[float, ...]:
    """Cacheia embeddings de queries individuais (resultados imutáveis)."""
    result = _post_with_retry([text])
    return tuple(result[0])


def embed_query(text: str) -> list[float] | None:
    """Gera embedding de uma query de busca. Retorna None se o serviço falhar."""
    if not text or not text.strip():
        return None
    try:
        return list(_embed_cached(text.strip()))
    except Exception as exc:
        logger.error("Falha ao gerar embedding da query: %s", exc)
        return None


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Gera embeddings em lote. Itens que falharem retornam None."""
    if not texts:
        return []
    try:
        results = _post_with_retry(texts)
        return results  # type: ignore[return-value]
    except Exception as exc:
        logger.error("Falha ao gerar embeddings em lote (%d textos): %s", len(texts), exc)
        return [None] * len(texts)


def service_available() -> bool:
    """Verifica se o serviço de embeddings está acessível."""
    try:
        resp = requests.get(f"{_EMBEDDINGS_URL}/health", timeout=5)
        return resp.ok and resp.json().get("ready", False)
    except Exception:
        return False
