"""
LangGraph multi-agent Q&A graph.

Agents:
  supervisor      – routes question to specialist or handles directly
  retrieval_agent – hybrid search + rerank
  synthesis_agent – LLM answer generation with citations
  eval_agent      – confidence scoring + hallucination guard
  fallback_agent  – handles out-of-scope / no-context questions
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
import structlog

from app.agents.state import AgentState, DocumentIngestionState
from app.config import settings

log = structlog.get_logger(__name__)


# ── LLM factory ──────────────────────────────────────────────────────────────


def _llm(temperature: float = 0.0) -> BaseChatModel:
    if settings.primary_llm == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        temperature=temperature,
    )


# ── Node functions ────────────────────────────────────────────────────────────


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Decide routing: retrieval | fallback."""
    llm = _llm(temperature=0.0)
    decision = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a routing supervisor. The user has uploaded documents "
                    "and is asking questions about them.\n"
                    "Reply with ONLY one word:\n"
                    "- 'retrieval' for ANY question that could be answered from a "
                    "document (default)\n"
                    "- 'fallback' ONLY if the question is clearly a system/technical "
                    "command unrelated to any document content\n"
                    "When in doubt, always choose retrieval."
                )
            ),
            HumanMessage(content=state["question"]),
        ]
    )
    route = decision.content.strip().lower()
    if route not in ("retrieval", "fallback"):
        route = "retrieval"
    log.info("supervisor_routed", question=state["question"][:80], route=route)
    return {"routed_to": route, "messages": [decision]}


async def query_expansion_node(state: AgentState) -> dict[str, Any]:
    """Generate 3 diverse sub-queries to improve recall."""
    llm = _llm(temperature=0.3)
    resp = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "Generate 3 diverse search queries for the given question. "
                    "Return ONLY the queries, one per line, no numbering."
                )
            ),
            HumanMessage(content=state["question"]),
        ]
    )
    queries = [q.strip() for q in resp.content.strip().split("\n") if q.strip()]
    return {"expanded_queries": queries[:3], "messages": [resp]}


async def retrieval_node(state: AgentState) -> dict[str, Any]:
    """Hybrid retrieval + cross-encoder reranking.

    Creates its own DB session instead of using the one passed from the route.
    LangGraph runs nodes via asyncio.create_task(), which resets SQLAlchemy's
    greenlet context — reusing a session from the parent task raises MissingGreenlet.
    """
    from app.database import AsyncSessionLocal
    from app.rag.reranker import CrossEncoderReranker
    from app.rag.retriever import HybridRetriever

    reranker = CrossEncoderReranker()
    queries = [state["question"]] + state.get("expanded_queries", [])
    all_chunks: list[dict[str, Any]] = []
    seen: set[str] = set()

    async with AsyncSessionLocal() as session:
        retriever = HybridRetriever(session)
        for q in queries:
            results = await retriever.retrieve(
                q,
                state.get("document_ids"),
                top_k=settings.retrieval_top_k,
                organization_id=state.get("organization_id"),
            )
            for r in results:
                key = str(r["id"])
                if key not in seen:
                    all_chunks.append(r)
                    seen.add(key)

    if all_chunks:
        final = await reranker.rerank(state["question"], all_chunks, top_k=settings.final_top_k)
    else:
        final = []

    msg = AIMessage(content=f"Retrieved {len(final)} chunks after reranking.")
    return {"retrieved_chunks": final, "messages": [msg]}


async def synthesis_node(state: AgentState) -> dict[str, Any]:
    """Generate cited answer from retrieved chunks."""
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "citations": [],
            "confidence": 0.0,
        }

    context_parts = []
    for i, c in enumerate(chunks, 1):
        context_parts.append(
            f"[{i}] Source: {c.get('original_name', 'Unknown')}, "
            f"Page {c.get('page_number', '?')}\n{c['content']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    llm = _llm(temperature=0.1)
    resp = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are an expert document analyst. Answer using ONLY the context below.\n"
                    "Cite sources inline as [Doc: <name>, Page: <n>].\n\n"
                    f"CONTEXT:\n{context}"
                )
            ),
            HumanMessage(content=state["question"]),
        ]
    )

    citations = [
        {
            "chunk_id": str(c["id"]),
            "document_id": str(c["document_id"]),
            "document_name": c.get("original_name", "Unknown"),
            "page_number": c.get("page_number"),
            "content": c["content"][:300],
            "relevance_score": float(c.get("rerank_score") or c.get("rrf_score") or 0),
        }
        for c in chunks
    ]
    return {"answer": resp.content, "citations": citations, "messages": [resp]}


async def eval_node(state: AgentState) -> dict[str, Any]:
    """Score answer quality / detect hallucinations."""
    if not state.get("answer") or not state.get("retrieved_chunks"):
        return {"confidence": 0.0}

    llm = _llm(temperature=0.0)
    resp = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "Given the question, answer, and source chunks, rate answer "
                    "confidence 0.0–1.0.\n"
                    "Consider: relevance, completeness, source support. Reply with ONLY a float."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {state['question']}\n\n"
                    f"Answer: {state['answer'][:500]}\n\n"
                    f"Sources: {len(state['retrieved_chunks'])} chunks retrieved"
                )
            ),
        ]
    )
    try:
        confidence = float(resp.content.strip())
        confidence = max(0.0, min(1.0, confidence))
    except ValueError:
        confidence = 0.7
    return {"confidence": confidence}


async def fallback_node(state: AgentState) -> dict[str, Any]:
    """Handle out-of-scope questions gracefully."""
    return {
        "answer": (
            "This question appears to be outside the scope of your uploaded documents. "
            "Please upload relevant PDFs and try again, or rephrase your question."
        ),
        "citations": [],
        "confidence": 0.0,
    }


# ── Routing functions ─────────────────────────────────────────────────────────


def route_after_supervisor(state: AgentState) -> Literal["expand", "fallback"]:
    return "fallback" if state.get("routed_to") == "fallback" else "expand"


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_qa_graph() -> Any:
    """Build and compile the Q&A agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("expand", query_expansion_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("synthesize", synthesis_node)
    graph.add_node("evaluate", eval_node)
    graph.add_node("fallback", fallback_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"expand": "expand", "fallback": "fallback"},
    )
    graph.add_edge("expand", "retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", "evaluate")
    graph.add_edge("evaluate", END)
    graph.add_edge("fallback", END)

    return graph.compile()


# ── Document ingestion graph ──────────────────────────────────────────────────


def build_ingestion_graph(db_url: str) -> Any:
    """Graph for async PDF ingestion pipeline.

    Accepts the DB URL string instead of a session — each node that needs DB
    creates its own session inside the LangGraph task context to avoid
    MissingGreenlet errors when asyncio.create_task() resets the greenlet.
    """

    async def parse_node(state: DocumentIngestionState) -> dict[str, Any]:
        from app.processors.pdf_processor import PDFProcessor

        proc = PDFProcessor()
        try:
            elements = await proc.process(state["file_path"])
            page_count = proc.get_page_count(state["file_path"])
            return {
                "elements": elements,
                "status": "parsed",
                "messages": [
                    AIMessage(content=f"Parsed {len(elements)} elements, {page_count} pages")
                ],
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def chunk_node(state: DocumentIngestionState) -> dict[str, Any]:
        from app.processors.chunker import DocumentChunker

        chunker = DocumentChunker()
        chunks = chunker.chunk_elements(state.get("elements", []))
        return {
            "chunks": chunks,
            "status": "chunked",
            "messages": [AIMessage(content=f"Created {len(chunks)} chunks")],
        }

    async def embed_node(state: DocumentIngestionState) -> dict[str, Any]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.models.document import Chunk, Document
        from app.rag.embeddings import get_embedder

        embedder = get_embedder()
        chunks = state.get("chunks", [])
        if not chunks:
            return {"status": "failed", "error": "No chunks to embed"}

        texts = [c["content"] for c in chunks]
        batch_size = 100
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            vecs = await embedder.embed(texts[i : i + batch_size])
            all_vectors.extend(vecs)

        engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=0)
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                stmt = select(Document).where(Document.id == state["document_id"])
                doc = (await session.execute(stmt)).scalar_one()

                chunk_objects = [
                    Chunk(
                        document_id=state["document_id"],
                        content=chunk_data["content"],
                        embedding=vector,
                        chunk_index=chunk_data["chunk_index"],
                        page_number=chunk_data.get("page_number"),
                        token_count=chunk_data.get("token_count"),
                        meta=chunk_data.get("metadata"),
                    )
                    for chunk_data, vector in zip(chunks, all_vectors, strict=False)
                ]
                session.add_all(chunk_objects)
                doc.chunk_count = len(chunk_objects)
                doc.status = "ready"
                await session.commit()
        finally:
            await engine.dispose()

        return {
            "embeddings_generated": True,
            "status": "ready",
            "messages": [AIMessage(content=f"Embedded {len(chunk_objects)} chunks")],
        }

    def route_after_parse(state: DocumentIngestionState) -> str:
        return "failed" if state.get("status") == "failed" else "chunk"

    async def failed_node(state: DocumentIngestionState) -> dict[str, Any]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.models.document import Document

        engine = create_async_engine(db_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                stmt = select(Document).where(Document.id == state["document_id"])
                doc = (await session.execute(stmt)).scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    doc.error_message = state.get("error", "Unknown error")
                    await session.commit()
        finally:
            await engine.dispose()
        return {"status": "failed"}

    graph = StateGraph(DocumentIngestionState)
    graph.add_node("parse", parse_node)
    graph.add_node("chunk", chunk_node)
    graph.add_node("embed", embed_node)
    graph.add_node("failed", failed_node)

    graph.set_entry_point("parse")
    graph.add_conditional_edges("parse", route_after_parse, {"chunk": "chunk", "failed": "failed"})
    graph.add_edge("chunk", "embed")
    graph.add_edge("embed", END)
    graph.add_edge("failed", END)

    return graph.compile()
