"""Hybrid retriever: pgvector dense search + BM25 sparse search, RRF fusion."""

from __future__ import annotations

from typing import Any
import uuid

from rank_bm25 import BM25Okapi
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.models.document import Chunk
from app.rag.embeddings import get_embedder

log = structlog.get_logger(__name__)


class HybridRetriever:
    """
    1. Dense retrieval via pgvector cosine similarity (HNSW index)
    2. Sparse retrieval via BM25 over stored chunk content
    3. Reciprocal Rank Fusion (RRF) to merge ranked lists
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._embedder = get_embedder()

    async def retrieve(
        self,
        query: str,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int = settings.retrieval_top_k,
        alpha: float = settings.hybrid_alpha,
        organization_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        query_vec = await self._embedder.embed_query(query)

        dense_results = await self._dense_search(query_vec, document_ids, top_k, organization_id)
        sparse_results = await self._sparse_search(query, document_ids, top_k, organization_id)

        fused = self._rrf_fusion(dense_results, sparse_results, k=60)
        return fused[:top_k]

    # ── Dense (pgvector) ─────────────────────────────────────
    async def _dense_search(
        self,
        query_vec: list[float],
        document_ids: list[uuid.UUID] | None,
        top_k: int,
        organization_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        filters = []
        if document_ids:
            ids = ", ".join(f"'{str(d)}'" for d in document_ids)
            filters.append(f"c.document_id IN ({ids})")
        if organization_id:
            filters.append(f"d.organization_id = '{organization_id}'::uuid")

        doc_filter = ""
        if filters:
            doc_filter = "AND " + " AND ".join(filters)

        sql = text(f"""
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.chunk_index,
                c.page_number,
                c.meta,
                d.original_name,
                1 - (c.embedding <=> '{vec_str}'::vector) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND d.status = 'ready'
              {doc_filter}
            ORDER BY c.embedding <=> '{vec_str}'::vector
            LIMIT :top_k
        """)  # noqa: S608
        rows = (await self._db.execute(sql, {"top_k": top_k})).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Sparse (BM25) ─────────────────────────────────────────
    async def _sparse_search(
        self,
        query: str,
        document_ids: list[uuid.UUID] | None,
        top_k: int,
        organization_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Chunk)
            .options(selectinload(Chunk.document))
            .join(Chunk.document)
            .where(Chunk.document.has(status="ready"))
        )
        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))
        if organization_id:
            stmt = stmt.where(Chunk.document.has(organization_id=organization_id))

        rows = (await self._db.execute(stmt)).scalars().all()
        if not rows:
            return []

        tokenized = [r.content.lower().split() for r in rows]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query.lower().split())

        scored = sorted(zip(scores, rows, strict=False), key=lambda x: x[0], reverse=True)
        return [
            {
                "id": row.id,
                "document_id": row.document_id,
                "content": row.content,
                "chunk_index": row.chunk_index,
                "page_number": row.page_number,
                "meta": row.meta,
                "original_name": row.document.original_name,
                "score": float(score),
            }
            for score, row in scored[:top_k]
        ]

    # ── RRF Fusion ────────────────────────────────────────────
    @staticmethod
    def _rrf_fusion(
        dense: list[dict[str, Any]],
        sparse: list[dict[str, Any]],
        k: int = 60,
    ) -> list[dict[str, Any]]:
        scores: dict[str, float] = {}
        meta: dict[str, dict[str, Any]] = {}

        for rank, item in enumerate(dense):
            key = str(item["id"])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            meta[key] = item

        for rank, item in enumerate(sparse):
            key = str(item["id"])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            meta.setdefault(key, item)

        sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
        return [{**meta[k], "rrf_score": scores[k]} for k in sorted_keys]
