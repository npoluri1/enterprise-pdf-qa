"""Celery tasks for async PDF ingestion."""
from __future__ import annotations

import asyncio
import uuid

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.workers.tasks.ingest_document",
)
def ingest_document(self, document_id: str, file_path: str) -> None:
    """Full ingestion pipeline: parse → chunk → embed → persist."""
    log.info("ingest_document_started", document_id=document_id)
    try:
        asyncio.run(_ingest(uuid.UUID(document_id), file_path))
        log.info("ingest_document_completed", document_id=document_id)
    except Exception as exc:
        log.error("ingest_document_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc)


async def _ingest(document_id: uuid.UUID, file_path: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings
    from app.agents.graph import build_ingestion_graph

    # Fresh engine per asyncio.run() call — the global pool's connections are
    # tied to whatever event loop last used them; each Celery task creates a new
    # loop via asyncio.run(), so we must start with a clean pool.
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
    )
    SessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        # Mark the document as processing
        async with SessionFactory() as db:
            await _set_status(db, document_id, "processing")

        # Graph nodes create their own sessions per LangGraph task context
        # (passing a session from here would cause MissingGreenlet inside create_task)
        graph = build_ingestion_graph(settings.database_url)
        await graph.ainvoke({
            "document_id": document_id,
            "file_path": file_path,
            "status": "processing",
            "elements": [],
            "chunks": [],
            "embeddings_generated": False,
            "error": None,
            "messages": [],
        })
    except Exception:
        # If the graph itself crashed (not just failed_node), mark it failed here
        engine2 = create_async_engine(settings.database_url, pool_pre_ping=True)
        SessionFactory2 = async_sessionmaker(bind=engine2, expire_on_commit=False)
        try:
            async with SessionFactory2() as db2:
                await _set_status(db2, document_id, "failed",
                                  error="Ingestion crashed — check worker logs")
        finally:
            await engine2.dispose()
        raise
    finally:
        await engine.dispose()


async def _set_status(
    db,
    document_id: uuid.UUID,
    status: str,
    error: str | None = None,
) -> None:
    from app.models.document import Document
    from sqlalchemy import select

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
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings
    from app.models.document import Document

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

    try:
        async with SessionFactory() as db:
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
