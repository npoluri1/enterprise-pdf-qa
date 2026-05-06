"""
Claude + MCP agentic Q&A.

Uses Anthropic's tool_use API so Claude can call document-search tools
in an agentic loop, gathering evidence before composing a final answer.
"""

from __future__ import annotations

import json
from typing import Any
import uuid

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.mcp.tools import ALL_MCP_TOOLS
from app.rag.reranker import CrossEncoderReranker
from app.rag.retriever import HybridRetriever
from app.schemas.qa import Citation

log = structlog.get_logger(__name__)

MAX_AGENT_TURNS = 6


class MCPDocumentServer:
    """
    Runs a Claude agentic loop:
      1. Claude decides which MCP tool to call
      2. We execute the tool against pgvector / postgres
      3. Tool result is fed back to Claude
      4. Repeat until Claude produces a final answer
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._retriever = HybridRetriever(db)
        self._reranker = CrossEncoderReranker()

    async def answer(
        self,
        question: str,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int = settings.final_top_k,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        collected_citations: list[Citation] = []
        turns = 0

        while turns < MAX_AGENT_TURNS:
            turns += 1
            resp = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=(
                    "You are an expert document analyst with access to document-search tools. "
                    "Always search the documents before answering. "
                    "Cite every fact as [Doc: <name>, Page: <n>]."
                ),
                tools=ALL_MCP_TOOLS,
                messages=messages,
            )

            # Append assistant turn
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "end_turn":
                # Final answer
                answer_text = " ".join(
                    block.text for block in resp.content if hasattr(block, "text")
                )
                return {
                    "answer": answer_text,
                    "citations": [c.model_dump() for c in collected_citations],
                    "model_used": f"anthropic/{settings.anthropic_model}",
                    "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                    "confidence": None,
                    "agent_turns": turns,
                }

            if resp.stop_reason == "tool_use":
                # Execute all tool calls in this turn
                tool_results: list[dict[str, Any]] = []
                for block in resp.content:
                    if block.type != "tool_use":
                        continue
                    result, new_citations = await self._execute_tool(
                        block.name, block.input, document_ids, top_k
                    )
                    collected_citations.extend(new_citations)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

        # Fallback if loop exhausted
        return {
            "answer": "Unable to complete the analysis within the allowed turns.",
            "citations": [],
            "model_used": f"anthropic/{settings.anthropic_model}",
            "tokens_used": None,
            "confidence": 0.0,
            "agent_turns": turns,
        }

    async def _execute_tool(
        self,
        name: str,
        inputs: dict[str, Any],
        document_ids: list[uuid.UUID] | None,
        top_k: int,
    ) -> tuple[dict[str, Any], list[Citation]]:
        if name == "search_documents":
            return await self._tool_search(inputs, document_ids, top_k)
        if name == "get_document_metadata":
            return await self._tool_metadata(inputs)
        if name == "list_documents":
            return await self._tool_list()
        return {"error": f"Unknown tool: {name}"}, []

    async def _tool_search(
        self, inputs: dict[str, Any], document_ids: list[uuid.UUID] | None, top_k: int
    ) -> tuple[dict[str, Any], list[Citation]]:
        query = inputs["query"]
        scoped_ids = inputs.get("document_ids")
        if scoped_ids:
            document_ids = [uuid.UUID(d) for d in scoped_ids]
        k = min(inputs.get("top_k", top_k), 20)

        candidates = await self._retriever.retrieve(
            query, document_ids, top_k=settings.retrieval_top_k
        )
        final = await self._reranker.rerank(query, candidates, top_k=k) if candidates else []

        passages = []
        citations: list[Citation] = []
        for c in final:
            passages.append(
                {
                    "text": c["content"],
                    "source": c.get("original_name", "Unknown"),
                    "page": c.get("page_number"),
                    "score": round(float(c.get("rerank_score") or c.get("rrf_score") or 0), 4),
                }
            )
            citations.append(
                Citation(
                    chunk_id=uuid.UUID(str(c["id"])),
                    document_id=uuid.UUID(str(c["document_id"])),
                    document_name=c.get("original_name", "Unknown"),
                    page_number=c.get("page_number"),
                    content=c["content"][:300],
                    relevance_score=float(c.get("rerank_score") or c.get("rrf_score") or 0),
                )
            )

        return {"passages": passages, "total_found": len(passages)}, citations

    async def _tool_metadata(self, inputs: dict[str, Any]) -> tuple[dict[str, Any], list[Citation]]:
        from sqlalchemy import select

        from app.models.document import Document

        doc_id = uuid.UUID(inputs["document_id"])
        stmt = select(Document).where(Document.id == doc_id)
        doc = (await self._db.execute(stmt)).scalar_one_or_none()
        if not doc:
            return {"error": "Document not found"}, []
        return {
            "id": str(doc.id),
            "name": doc.original_name,
            "pages": doc.page_count,
            "chunks": doc.chunk_count,
            "status": doc.status,
            "uploaded_at": doc.created_at.isoformat(),
        }, []

    async def _tool_list(self) -> tuple[dict[str, Any], list[Citation]]:
        from sqlalchemy import select

        from app.models.document import Document

        stmt = select(Document).where(Document.status == "ready")
        docs = (await self._db.execute(stmt)).scalars().all()
        return {
            "documents": [
                {"id": str(d.id), "name": d.original_name, "pages": d.page_count} for d in docs
            ]
        }, []
