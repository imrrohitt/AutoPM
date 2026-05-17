"""Local embeddings via fastembed (no external API)."""

from __future__ import annotations

import logging
from functools import lru_cache

from core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _model_name() -> str:
    return get_settings().EMBEDDING_MODEL


@lru_cache
def _embedding_model():
    from fastembed import TextEmbedding

    name = _model_name()
    logger.info("Loading fastembed model: %s", name)
    return TextEmbedding(model_name=name)


def embed_text(text: str) -> list[float]:
    vectors = embed_texts([text])
    return vectors[0] if vectors else []


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    cleaned = [t.strip()[:8000] or " " for t in texts]
    model = _embedding_model()
    return [list(v) for v in model.embed(cleaned)]
