"""
Core RAG pipeline built with LangChain.

Flow:
  question → query expansion → hybrid retrieval → reranking → LLM answer + citations
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator

import structlog
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.rag.embeddings import get_embedder
from app.rag.retriever import HybridRetriever
from app.rag.reranker import CrossEncoderReranker
from app.schemas.qa import Citation

log = structlog.get_logger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────────────

QUERY_EXPANSION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a search query optimizer. Given a user question, generate 3 diverse search queries that together would retrieve the most relevant document passages. Return ONLY the queries, one per line."),
    ("human", "{question}"),
])

QA_SYSTEM_PROMPT = """You are an expert enterprise document analyst. Answer the user's question accurately and concisely using ONLY the provided context.

Rules:
- Cite every factual claim using [Doc: {doc_name}, Page: {page}] format inline
- If the answer is not in the context, say "I couldn't find this information in the provided documents."
- Be precise and professional
- Structure longer answers with bullet points or numbered lists when appropriate

Context:
{context}"""

QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", QA_SYSTEM_PROMPT),
    ("human", "{question}"),
])


def _get_llm(streaming: bool = False):
    if settings.primary_llm == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            streaming=streaming,
            max_tokens=2048,
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        streaming=streaming,
        temperature=0.1,
        max_tokens=2048,
    )


class RAGPipeline:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._retriever = HybridRetriever(db)
        self._reranker = CrossEncoderReranker()

    async def run(
        self,
        question: str,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int = settings.final_top_k,
        use_reranker: bool = True,
    ) -> dict[str, Any]:
        # 1. Query expansion via LLM
        expanded = await self._expand_query(question)
        all_queries = [question] + expanded

        # 2. Retrieve candidates for all queries
        all_candidates: list[dict] = []
        seen_ids: set = set()
        for q in all_queries:
            results = await self._retriever.retrieve(q, document_ids, top_k=settings.retrieval_top_k)
            for r in results:
                if str(r["id"]) not in seen_ids:
                    all_candidates.append(r)
                    seen_ids.add(str(r["id"]))

        # 3. Rerank
        if use_reranker and all_candidates:
            final_chunks = await self._reranker.rerank(question, all_candidates, top_k=top_k)
        else:
            final_chunks = sorted(all_candidates, key=lambda x: x.get("rrf_score", 0), reverse=True)[:top_k]

        if not final_chunks:
            return {
                "answer": "No relevant documents found. Please upload documents first.",
                "citations": [],
                "model_used": settings.primary_llm,
                "tokens_used": None,
                "confidence": 0.0,
            }

        # 4. Build context
        context = self._build_context(final_chunks)

        # 5. LLM generation
        llm = _get_llm()
        chain = QA_PROMPT | llm | StrOutputParser()
        answer = await chain.ainvoke({"question": question, "context": context})

        # 6. Build citations
        citations = self._build_citations(final_chunks)

        return {
            "answer": answer,
            "citations": citations,
            "model_used": f"{settings.primary_llm}/{settings.openai_model if settings.primary_llm == 'openai' else settings.anthropic_model}",
            "tokens_used": None,
            "confidence": final_chunks[0].get("rerank_score") if use_reranker else None,
        }

    async def stream(
        self,
        question: str,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int = settings.final_top_k,
        use_reranker: bool = True,
    ) -> AsyncGenerator[dict, None]:
        # Retrieve and rerank first
        all_candidates = await self._retriever.retrieve(question, document_ids, top_k=settings.retrieval_top_k)
        if use_reranker and all_candidates:
            final_chunks = await self._reranker.rerank(question, all_candidates, top_k=top_k)
        else:
            final_chunks = all_candidates[:top_k]

        context = self._build_context(final_chunks)
        citations = self._build_citations(final_chunks)

        # Yield citations first
        yield {"type": "citation", "citations": citations}

        # Stream answer tokens
        llm = _get_llm(streaming=True)
        chain = QA_PROMPT | llm | StrOutputParser()
        async for token in chain.astream({"question": question, "context": context}):
            yield {"type": "token", "content": token}

        yield {"type": "done", "content": ""}

    async def _expand_query(self, question: str) -> list[str]:
        try:
            llm = _get_llm()
            chain = QUERY_EXPANSION_PROMPT | llm | StrOutputParser()
            result = await chain.ainvoke({"question": question})
            return [q.strip() for q in result.strip().split("\n") if q.strip()][:3]
        except Exception:
            return []

    @staticmethod
    def _build_context(chunks: list[dict]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            doc = c.get("original_name", "Unknown")
            page = c.get("page_number", "?")
            parts.append(f"[{i}] Doc: {doc}, Page: {page}\n{c['content']}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _build_citations(chunks: list[dict]) -> list[Citation]:
        return [
            Citation(
                chunk_id=uuid.UUID(str(c["id"])),
                document_id=uuid.UUID(str(c["document_id"])),
                document_name=c.get("original_name", "Unknown"),
                page_number=c.get("page_number"),
                content=c["content"][:300],
                relevance_score=float(c.get("rerank_score") or c.get("rrf_score") or 0),
            )
            for c in chunks
        ]
