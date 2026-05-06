"""LangGraph agent node unit tests."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _base_state(**overrides) -> dict:
    return {
        "question": "What is the risk level?",
        "document_ids": None,
        "user_id": uuid.uuid4(),
        "retrieved_chunks": [],
        "expanded_queries": [],
        "routed_to": "",
        "answer": "",
        "citations": [],
        "confidence": None,
        "error": None,
        "messages": [],
        "iteration": 0,
        **overrides,
    }


@pytest.mark.unit
class TestSupervisorNode:
    async def test_routes_to_retrieval_for_document_question(self):
        from app.agents.graph import supervisor_node

        mock_llm_response = MagicMock()
        mock_llm_response.content = "retrieval"

        with patch("app.agents.graph._llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
            mock_llm_factory.return_value = mock_llm

            result = await supervisor_node(_base_state())

        assert result["routed_to"] == "retrieval"

    async def test_routes_to_fallback_for_off_topic(self):
        from app.agents.graph import supervisor_node

        mock_llm_response = MagicMock()
        mock_llm_response.content = "fallback"

        with patch("app.agents.graph._llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
            mock_llm_factory.return_value = mock_llm

            result = await supervisor_node(_base_state(question="What is the weather?"))

        assert result["routed_to"] == "fallback"

    async def test_defaults_to_retrieval_on_unexpected_response(self):
        from app.agents.graph import supervisor_node

        mock_llm_response = MagicMock()
        mock_llm_response.content = "unknown_route"

        with patch("app.agents.graph._llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
            mock_llm_factory.return_value = mock_llm

            result = await supervisor_node(_base_state())

        assert result["routed_to"] == "retrieval"


@pytest.mark.unit
class TestQueryExpansionNode:
    async def test_generates_three_queries(self):
        from app.agents.graph import query_expansion_node

        mock_resp = MagicMock()
        mock_resp.content = "Query one\nQuery two\nQuery three"

        with patch("app.agents.graph._llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
            mock_factory.return_value = mock_llm

            result = await query_expansion_node(_base_state())

        assert len(result["expanded_queries"]) == 3

    async def test_caps_at_three_queries(self):
        from app.agents.graph import query_expansion_node

        mock_resp = MagicMock()
        mock_resp.content = "Query 1\nQuery 2\nQuery 3\nQuery 4\nQuery 5"

        with patch("app.agents.graph._llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
            mock_factory.return_value = mock_llm

            result = await query_expansion_node(_base_state())

        assert len(result["expanded_queries"]) <= 3


@pytest.mark.unit
class TestFallbackNode:
    async def test_fallback_returns_out_of_scope_message(self):
        from app.agents.graph import fallback_node

        result = await fallback_node(_base_state())

        assert "outside the scope" in result["answer"].lower()
        assert result["citations"] == []
        assert result["confidence"] == 0.0


@pytest.mark.unit
class TestSynthesisNode:
    async def test_synthesis_with_no_chunks_returns_empty(self):
        from app.agents.graph import synthesis_node

        result = await synthesis_node(_base_state(retrieved_chunks=[]))

        assert "couldn't find" in result["answer"].lower()
        assert result["citations"] == []

    async def test_synthesis_builds_citations_from_chunks(self):
        from app.agents.graph import synthesis_node

        chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "The risk level is high.",
                "page_number": 3,
                "original_name": "risk_report.pdf",
                "rerank_score": 0.9,
            }
        ]

        mock_resp = MagicMock()
        mock_resp.content = "The risk level is high [Doc: risk_report.pdf, Page: 3]."

        with patch("app.agents.graph._llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
            mock_factory.return_value = mock_llm

            result = await synthesis_node(_base_state(retrieved_chunks=chunks))

        assert len(result["citations"]) == 1
        assert result["citations"][0]["document_name"] == "risk_report.pdf"


@pytest.mark.unit
class TestRoutingFunctions:
    def test_route_after_supervisor_to_expand(self):
        from app.agents.graph import route_after_supervisor

        state = _base_state(routed_to="retrieval")
        assert route_after_supervisor(state) == "expand"

    def test_route_after_supervisor_to_fallback(self):
        from app.agents.graph import route_after_supervisor

        state = _base_state(routed_to="fallback")
        assert route_after_supervisor(state) == "fallback"
