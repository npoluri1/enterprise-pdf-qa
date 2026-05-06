"""Q&A endpoint tests."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.document import Chunk, Document
from app.models.user import User


def _mock_graph_result(answer: str = "Test answer from document.") -> dict:
    return {
        "answer": answer,
        "citations": [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "test.pdf",
                "page_number": 1,
                "content": "Test content excerpt.",
                "relevance_score": 0.92,
            }
        ],
        "confidence": 0.87,
        "model_used": "openai/gpt-4o",
        "tokens_used": None,
    }


@pytest.mark.integration
class TestAsk:
    async def test_ask_returns_answer(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_document: Document,
        test_chunks: list[Chunk],
    ):
        mock_result = _mock_graph_result()
        with patch("app.api.routes.qa.build_qa_graph") as mock_build:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            mock_build.return_value = mock_graph

            resp = await client.post(
                "/api/v1/qa/ask",
                headers=auth_headers,
                json={
                    "question": "What does this document say?",
                    "document_ids": [str(test_document.id)],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == mock_result["answer"]
        assert isinstance(data["citations"], list)
        assert "confidence" in data

    async def test_ask_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/qa/ask",
            json={"question": "What is this?", "document_ids": []},
        )
        assert resp.status_code == 401

    async def test_ask_question_too_short(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/qa/ask",
            headers=auth_headers,
            json={"question": "Hi"},
        )
        assert resp.status_code == 422

    async def test_ask_question_too_long(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/qa/ask",
            headers=auth_headers,
            json={"question": "x" * 2001},
        )
        assert resp.status_code == 422

    async def test_ask_without_document_ids_scans_all(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_document: Document,
        test_chunks: list[Chunk],
    ):
        mock_result = _mock_graph_result()
        with patch("app.api.routes.qa.build_qa_graph") as mock_build:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            mock_build.return_value = mock_graph

            resp = await client.post(
                "/api/v1/qa/ask",
                headers=auth_headers,
                json={"question": "Tell me about this document."},
            )
        assert resp.status_code == 200


@pytest.mark.integration
class TestHealth:
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
