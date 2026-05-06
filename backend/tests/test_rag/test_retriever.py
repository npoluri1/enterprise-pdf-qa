"""Hybrid retriever unit tests."""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.unit
class TestRRFFusion:
    def test_rrf_combines_scores(self):
        from app.rag.retriever import HybridRetriever

        id1, id2, id3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        dense = [
            {"id": id1, "content": "A", "document_id": "d1", "score": 0.9},
            {"id": id2, "content": "B", "document_id": "d1", "score": 0.7},
        ]
        sparse = [
            {"id": id2, "content": "B", "document_id": "d1", "score": 0.8},
            {"id": id3, "content": "C", "document_id": "d1", "score": 0.6},
        ]

        result = HybridRetriever._rrf_fusion(dense, sparse, k=60)

        ids_in_result = [str(r["id"]) for r in result]
        assert id1 in ids_in_result
        assert id2 in ids_in_result
        assert id3 in ids_in_result

        # id2 appears in both lists so it should rank highest
        assert ids_in_result[0] == id2

    def test_rrf_empty_dense(self):
        from app.rag.retriever import HybridRetriever

        id1 = str(uuid.uuid4())
        sparse = [{"id": id1, "content": "A", "document_id": "d1", "score": 0.9}]

        result = HybridRetriever._rrf_fusion([], sparse, k=60)
        assert len(result) == 1
        assert str(result[0]["id"]) == id1

    def test_rrf_empty_both(self):
        from app.rag.retriever import HybridRetriever
        result = HybridRetriever._rrf_fusion([], [], k=60)
        assert result == []

    def test_rrf_score_decreases_with_rank(self):
        from app.rag.retriever import HybridRetriever

        items = [{"id": str(uuid.uuid4()), "content": f"text {i}", "document_id": "d"} for i in range(5)]
        result = HybridRetriever._rrf_fusion(items, [], k=60)

        scores = [r["rrf_score"] for r in result]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
class TestChunkerIntegration:
    def test_chunker_splits_long_text(self):
        from app.processors.chunker import DocumentChunker

        chunker = DocumentChunker(chunk_size=100, chunk_overlap=10)
        elements = [
            {
                "text": "word " * 200,
                "page_number": 1,
                "element_type": "NarrativeText",
                "metadata": {},
            }
        ]
        chunks = chunker.chunk_elements(elements)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk["content"]) <= 200  # some leeway for overlap

    def test_chunker_preserves_page_number(self):
        from app.processors.chunker import DocumentChunker

        chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)
        elements = [{"text": "Short text.", "page_number": 7, "element_type": "Title", "metadata": {}}]
        chunks = chunker.chunk_elements(elements)
        assert all(c["page_number"] == 7 for c in chunks)

    def test_chunker_skips_empty_elements(self):
        from app.processors.chunker import DocumentChunker

        chunker = DocumentChunker()
        elements = [{"text": "", "page_number": 1, "element_type": "Text", "metadata": {}}]
        chunks = chunker.chunk_elements(elements)
        assert len(chunks) == 0

    def test_chunker_assigns_sequential_indices(self):
        from app.processors.chunker import DocumentChunker

        chunker = DocumentChunker(chunk_size=50, chunk_overlap=5)
        elements = [
            {"text": "word " * 20, "page_number": 1, "element_type": "Text", "metadata": {}},
            {"text": "word " * 20, "page_number": 2, "element_type": "Text", "metadata": {}},
        ]
        chunks = chunker.chunk_elements(elements)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))
