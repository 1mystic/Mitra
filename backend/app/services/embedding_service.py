"""Singleton sentence-transformers model for all embedding operations."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from ..config import settings

_executor = ThreadPoolExecutor(max_workers=2)


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def _encode_sync(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text, normalize_embeddings=True, show_progress_bar=False).tolist()


def _encode_batch_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
        convert_to_numpy=True,
    ).tolist()


async def embed(text: str) -> list[float]:
    """Embed a single text string. Runs in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _encode_sync, text)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in one batch call."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _encode_batch_sync, texts)
