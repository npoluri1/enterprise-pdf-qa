"""Celery tasks for async PDF ingestion."""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import Any
import uuid

import structlog

from app.agents.graph import build_ingestion_graph
from app.database import AsyncSessionLocal
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.workers.tasks.ingest_document",
)
def ingest_document(self, document_id: str, file_path: str) -> None:  # noqa: ANN001
    """Full ingestion pipeline: parse → chunk → embed → persist."""
    log.info("ingest_document_started", document_id=document_id)
    try:
        asyncio.run(_ingest(uuid.UUID(document_id), file_path))
        log.info("ingest_document_completed", document_id=document_id)
    except Exception as exc:
        log.error("ingest_document_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc) from exc


async def _ingest(document_id: uuid.UUID, file_path: str) -> None:
    from app.config import settings

    async with AsyncSessionLocal() as db:
        await _set_status(db, document_id, "processing")

    graph = build_ingestion_graph(settings.database_url)
    try:
        await graph.ainvoke(
            {
                "document_id": document_id,
                "file_path": file_path,
                "status": "processing",
                "elements": [],
                "chunks": [],
                "embeddings_generated": False,
                "error": None,
                "messages": [],
            }
        )
    except Exception:
        async with AsyncSessionLocal() as db:
            await _set_status(
                db, document_id, "failed", error="Ingestion crashed — check worker logs"
            )
        raise


async def _set_status(
    db: Any,
    document_id: uuid.UUID,
    status: str,
    error: str | None = None,
) -> None:
    from sqlalchemy import select

    from app.models.document import Document

    stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if doc:
        doc.status = status
        if error:
            doc.error_message = error
        await db.commit()


@celery_app.task(name="app.workers.tasks.cleanup_failed_documents")
def cleanup_failed_documents() -> None:
    """Mark documents stuck in 'processing' for > 2 hours as failed."""
    log.info("cleanup_task_started")
    asyncio.run(_cleanup())


async def _cleanup() -> None:
    from datetime import datetime, timedelta

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models.document import Document

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    cutoff = datetime.now(UTC) - timedelta(hours=2)

    try:
        async with session_factory() as db:
            stmt = (
                update(Document)
                .where(Document.status == "processing", Document.created_at < cutoff)
                .values(status="failed", error_message="Ingestion timed out")
            )
            result = await db.execute(stmt)
            await db.commit()
            log.info("cleanup_completed", rows_updated=result.rowcount)
    finally:
        await engine.dispose()
