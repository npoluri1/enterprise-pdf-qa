"""Celery task unit tests."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestIngestDocument:
    def test_ingest_document_calls_ingestion_graph(self):
        from app.workers.tasks import ingest_document

        doc_id = str(uuid.uuid4())
        file_path = "/tmp/test.pdf"

        with patch("app.workers.tasks._ingest", new=AsyncMock()) as mock_ingest:
            with patch("app.workers.tasks.asyncio.run") as mock_run:
                ingest_document(doc_id, file_path)
                mock_run.assert_called_once()

    def test_ingest_document_retries_on_failure(self):
        from celery.exceptions import Retry
        from app.workers.tasks import ingest_document

        doc_id = str(uuid.uuid4())

        with patch("app.workers.tasks.asyncio.run", side_effect=RuntimeError("DB error")):
            with pytest.raises((Retry, RuntimeError)):
                ingest_document.run(doc_id, "/tmp/test.pdf")


@pytest.mark.unit
class TestCleanupTask:
    def test_cleanup_calls_async_cleanup(self):
        from app.workers.tasks import cleanup_failed_documents

        with patch("app.workers.tasks._cleanup", new=AsyncMock()) as mock_cleanup:
            with patch("app.workers.tasks.asyncio.run") as mock_run:
                cleanup_failed_documents()
                mock_run.assert_called_once()


@pytest.mark.unit
class TestIngestAsync:
    async def test_ingest_runs_graph(self):
        from app.workers.tasks import _ingest

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={"status": "ready"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.workers.tasks.AsyncSessionLocal", return_value=mock_session),
            patch("app.workers.tasks.build_ingestion_graph", return_value=mock_graph),
        ):
            await _ingest(uuid.uuid4(), "/tmp/test.pdf")

        mock_graph.ainvoke.assert_called_once()

    async def test_ingest_passes_correct_initial_state(self):
        from app.workers.tasks import _ingest

        doc_id = uuid.uuid4()
        file_path = "/tmp/specific_file.pdf"
        captured_state = {}

        async def capture_state(state):
            captured_state.update(state)
            return {"status": "ready"}

        mock_graph = MagicMock()
        mock_graph.ainvoke = capture_state

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.workers.tasks.AsyncSessionLocal", return_value=mock_session),
            patch("app.workers.tasks.build_ingestion_graph", return_value=mock_graph),
        ):
            await _ingest(doc_id, file_path)

        assert captured_state["document_id"] == doc_id
        assert captured_state["file_path"] == file_path
        assert captured_state["status"] == "processing"
