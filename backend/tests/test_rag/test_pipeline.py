"""RAG pipeline unit tests."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_chunk(content: str = "Test content.", page: int = 1) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "content": content,
        "page_number": page,
        "original_name": "test.pdf",
        "rrf_score": 0.5,
        "rerank_score": 0.8,
    }


@pytest.mark.unit
class TestRAGPipelineBuildContext:
    def test_build_context_formats_correctly(self):
        from app.rag.pipeline import RAGPipeline
        chunks = [_make_chunk("First passage.", 1), _make_chunk("Second passage.", 3)]
        context = RAGPipeline._build_context(chunks)
        assert "[1]" in context
        assert "[2]" in context
        assert "First passage." in context
        assert "Second passage." in context
        assert "test.pdf" in context

    def test_build_context_empty_chunks(self):
        from app.rag.pipeline import RAGPipeline
        context = RAGPipeline._build_context([])
        assert context == ""


@pytest.mark.unit
class TestRAGPipelineBuildCitations:
    def test_build_citations_returns_citation_objects(self):
        from app.rag.pipeline import RAGPipeline
        from app.schemas.qa import Citation

        chunks = [_make_chunk()]
        citations = RAGPipeline._build_citations(chunks)
        assert len(citations) == 1
        assert isinstance(citations[0], Citation)
        assert citations[0].document_name == "test.pdf"

    def test_build_citations_caps_content_at_300_chars(self):
        from app.rag.pipeline import RAGPipeline

        chunk = _make_chunk("word " * 100)  # ~500 chars
        citations = RAGPipeline._build_citations([chunk])
        assert len(citations[0].content) <= 300


@pytest.mark.unit
class TestRAGPipelineRun:
    async def test_run_returns_answer_and_citations(self):
        from app.rag.pipeline import RAGPipeline

        mock_db = MagicMock()
        chunks = [_make_chunk("The answer is in this document.", 2)]

        with (
            patch("app.rag.pipeline.HybridRetriever") as MockRetriever,
            patch("app.rag.pipeline.CrossEncoderReranker") as MockReranker,
            patch("app.rag.pipeline.RAGPipeline._expand_query", new=AsyncMock(return_value=[])),
            patch("app.rag.pipeline.QA_PROMPT") as mock_prompt,
        ):
            MockRetriever.return_value.retrieve = AsyncMock(return_value=chunks)
            MockReranker.return_value.rerank = AsyncMock(return_value=chunks)

            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value="The answer is...")
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            pipeline = RAGPipeline(mock_db)
            result = await pipeline.run("What is the answer?")

        assert "answer" in result
        assert "citations" in result

    async def test_run_returns_no_docs_message_when_empty(self):
        from app.rag.pipeline import RAGPipeline

        mock_db = MagicMock()

        with (
            patch("app.rag.pipeline.HybridRetriever") as MockRetriever,
            patch("app.rag.pipeline.CrossEncoderReranker") as MockReranker,
            patch("app.rag.pipeline.RAGPipeline._expand_query", new=AsyncMock(return_value=[])),
        ):
            MockRetriever.return_value.retrieve = AsyncMock(return_value=[])
            MockReranker.return_value.rerank = AsyncMock(return_value=[])

            pipeline = RAGPipeline(mock_db)
            result = await pipeline.run("What is the answer?")

        assert "No relevant documents" in result["answer"]
        assert result["citations"] == []
