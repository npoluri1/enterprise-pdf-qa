"""
Q&A endpoints.

POST /api/v1/qa/ask          – standard RAG (LangGraph multi-agent)
POST /api/v1/qa/ask/mcp      – Claude + MCP agentic loop
GET  /api/v1/qa/stream       – SSE streaming answer
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_qa_graph
from app.core.dependencies import get_current_user
from app.database import get_db
from app.mcp.server import MCPDocumentServer
from app.models.user import User
from app.schemas.qa import QuestionRequest, QuestionResponse

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=QuestionResponse)
async def ask(
    payload: QuestionRequest,
    current_user: User = Depends(get_current_user),
) -> QuestionResponse:
    """Multi-agent LangGraph RAG pipeline."""
    graph = build_qa_graph()
    result = await graph.ainvoke(
        {
            "question": payload.question,
            "document_ids": payload.document_ids,
            "user_id": current_user.id,
            "retrieved_chunks": [],
            "expanded_queries": [],
            "routed_to": "",
            "answer": "",
            "citations": [],
            "confidence": None,
            "error": None,
            "messages": [],
            "iteration": 0,
        }
    )
    return QuestionResponse(
        question=payload.question,
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        model_used=result.get("model_used", "langgraph"),
        tokens_used=result.get("tokens_used"),
        confidence=result.get("confidence"),
    )


@router.post("/ask/mcp", response_model=QuestionResponse)
async def ask_mcp(
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionResponse:
    """Claude + MCP tool-use agentic loop (Anthropic)."""
    import anthropic as anthropic_sdk
    from fastapi import HTTPException

    from app.config import settings

    key = settings.anthropic_api_key
    if not key or key.startswith("sk-ant-...") or key == "sk-ant-":
        raise HTTPException(
            status_code=503,
            detail=(
                "Claude + MCP mode requires a valid Anthropic API key. "
                "Set ANTHROPIC_API_KEY in your .env file, then restart: "
                "docker compose down && docker compose up -d"
            ),
        )

    try:
        server = MCPDocumentServer(db)
        result = await server.answer(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except anthropic_sdk.AuthenticationError as err:
        raise HTTPException(
            status_code=503,
            detail=(
                "Anthropic API key is invalid or expired. "
                "Update ANTHROPIC_API_KEY in .env, then restart: "
                "docker compose down && docker compose up -d"
            ),
        ) from err
    except anthropic_sdk.RateLimitError as err:
        raise HTTPException(
            status_code=503, detail="Anthropic rate limit reached — try again shortly."
        ) from err
    except anthropic_sdk.APIConnectionError as err:
        raise HTTPException(
            status_code=503, detail="Cannot reach Anthropic API — check network connectivity."
        ) from err

    return QuestionResponse(
        question=payload.question,
        answer=result["answer"],
        citations=result.get("citations", []),
        model_used=result.get("model_used", "mcp"),
        tokens_used=result.get("tokens_used"),
        confidence=result.get("confidence"),
        meta={"agent_turns": result.get("agent_turns")},
    )


@router.post("/ask/stream")
async def ask_stream(
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Server-Sent Events streaming answer."""
    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(db)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for chunk in pipeline.stream(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
            use_reranker=payload.use_reranker,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
