"""Embedding factory – OpenAI text-embedding-3-large or HuggingFace BGE."""
from __future__ import annotations

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def get_embedder():
    """Return a callable embed(texts: list[str]) -> list[list[float]]."""
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder()
    return HuggingFaceEmbedder()


class OpenAIEmbedder:
    def __init__(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimension = settings.embedding_dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimension,
        )
        return [item.embedding for item in resp.data]

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]


class HuggingFaceEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(settings.hf_embedding_model)
        self.dimension = self._model.get_sentence_embedding_dimension()
        log.info("hf_embedder_loaded", model=settings.hf_embedding_model, dim=self.dimension)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None, lambda: self._model.encode(texts, normalize_embeddings=True).tolist()
        )
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]
