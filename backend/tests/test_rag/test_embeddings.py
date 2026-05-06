"""Embedder unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings


@pytest.mark.unit
class TestOpenAIEmbedder:
    async def test_embed_returns_correct_shape(self):
        from app.rag.embeddings import OpenAIEmbedder

        fake_vector = [0.1] * settings.embedding_dimension
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_vector)]

        with patch("app.rag.embeddings.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.embeddings.create = AsyncMock(return_value=mock_response)
            embedder = OpenAIEmbedder()
            embedder._client = instance

            result = await embedder.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == settings.embedding_dimension

    async def test_embed_query_returns_single_vector(self):
        from app.rag.embeddings import OpenAIEmbedder

        fake_vector = [0.5] * settings.embedding_dimension
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_vector)]

        with patch("app.rag.embeddings.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.embeddings.create = AsyncMock(return_value=mock_response)
            embedder = OpenAIEmbedder()
            embedder._client = instance

            result = await embedder.embed_query("single query")

        assert isinstance(result, list)
        assert len(result) == settings.embedding_dimension

    async def test_embed_batch_multiple_texts(self):
        from app.rag.embeddings import OpenAIEmbedder

        n = 3
        fake_vectors = [[float(i)] * settings.embedding_dimension for i in range(n)]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=v) for v in fake_vectors]

        with patch("app.rag.embeddings.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.embeddings.create = AsyncMock(return_value=mock_response)
            embedder = OpenAIEmbedder()
            embedder._client = instance

            result = await embedder.embed(["text1", "text2", "text3"])

        assert len(result) == n


@pytest.mark.unit
class TestGetEmbedder:
    def test_returns_openai_when_configured(self):
        from app.rag.embeddings import OpenAIEmbedder, get_embedder

        with patch.object(settings, "embedding_provider", "openai"):
            embedder = get_embedder()
        assert isinstance(embedder, OpenAIEmbedder)

    def test_returns_huggingface_when_configured(self):
        from app.rag.embeddings import HuggingFaceEmbedder, get_embedder

        with patch.object(settings, "embedding_provider", "huggingface"):
            with patch("app.rag.embeddings.SentenceTransformer" if False else "sentence_transformers.SentenceTransformer"):
                with patch("app.rag.embeddings.HuggingFaceEmbedder") as MockHF:
                    MockHF.return_value = MagicMock()
                    embedder = get_embedder()
