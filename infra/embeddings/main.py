"""Serviço mínimo de embeddings com sentence-transformers."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("embeddings")

MODEL_NAME = os.getenv("EMBEDDINGS_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

app = FastAPI(title="AnCo Embeddings")

# Carrega o modelo uma vez na inicialização do processo.
model: SentenceTransformer | None = None


@app.on_event("startup")
def load_model() -> None:
    global model
    logger.info("Carregando modelo %s …", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME, cache_folder="/model_cache")
    logger.info("Modelo pronto. Dimensões: %d", model.get_sentence_embedding_dimension())


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimensions: int


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    assert model is not None  # noqa: S101
    vecs = model.encode(req.texts, normalize_embeddings=True).tolist()
    return EmbedResponse(embeddings=vecs, dimensions=len(vecs[0]) if vecs else 0)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "ready": model is not None}
