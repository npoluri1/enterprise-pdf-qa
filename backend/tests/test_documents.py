"""Document upload, list, delete endpoint tests."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.document import Document
from app.models.user import User


@pytest.mark.integration
class TestUpload:
    async def test_upload_pdf_success(
        self, client: AsyncClient, auth_headers: dict, minimal_pdf: bytes
    ):
        with patch("app.api.routes.documents.ingest_document") as mock_task:
            mock_task.apply_async = MagicMock()
            resp = await client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("report.pdf", io.BytesIO(minimal_pdf), "application/pdf")},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_name"] == "report.pdf"
        assert data["status"] == "pending"
        assert "id" in data

    async def test_upload_requires_auth(self, client: AsyncClient, minimal_pdf: bytes):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("report.pdf", io.BytesIO(minimal_pdf), "application/pdf")},
        )
        assert resp.status_code == 401

    async def test_upload_non_pdf_rejected(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("image.png", io.BytesIO(b"PNG data"), "image/png")},
        )
        assert resp.status_code == 400

    async def test_upload_oversized_rejected(
        self, client: AsyncClient, auth_headers: dict
    ):
        big_pdf = b"%PDF-1.4" + b"x" * (51 * 1024 * 1024)
        resp = await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("big.pdf", io.BytesIO(big_pdf), "application/pdf")},
        )
        assert resp.status_code == 413

    async def test_upload_triggers_celery_task(
        self, client: AsyncClient, auth_headers: dict, minimal_pdf: bytes
    ):
        with patch("app.api.routes.documents.ingest_document") as mock_task:
            mock_apply = MagicMock()
            mock_task.apply_async = mock_apply

            await client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("report.pdf", io.BytesIO(minimal_pdf), "application/pdf")},
            )
        mock_apply.assert_called_once()


@pytest.mark.integration
class TestList:
    async def test_list_returns_own_documents(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_document: Document,
    ):
        resp = await client.get("/api/v1/documents/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [d["id"] for d in data["items"]]
        assert str(test_document.id) in ids

    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/documents/")
        assert resp.status_code == 401

    async def test_list_does_not_return_other_users_docs(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
        db_session,
    ):
        from app.core.security import hash_password
        from app.core.security import create_access_token
        import uuid

        other_user = User(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Pass123!"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_doc = Document(
            owner_id=other_user.id,
            filename=f"{uuid.uuid4()}.pdf",
            original_name="other.pdf",
            file_path="/tmp/other.pdf",
            file_size=512,
            status="ready",
        )
        db_session.add(other_doc)
        await db_session.commit()

        resp = await client.get("/api/v1/documents/", headers=auth_headers)
        ids = [d["id"] for d in resp.json()["items"]]
        assert str(other_doc.id) not in ids


@pytest.mark.integration
class TestDelete:
    async def test_delete_own_document(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_document: Document,
    ):
        with patch("app.api.routes.documents.os.remove"):
            resp = await client.delete(
                f"/api/v1/documents/{test_document.id}",
                headers=auth_headers,
            )
        assert resp.status_code == 204

    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict):
        import uuid
        resp = await client.delete(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_delete_other_users_document_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
    ):
        from app.core.security import hash_password
        import uuid

        other_user = User(
            email=f"other2-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Pass123!"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_doc = Document(
            owner_id=other_user.id,
            filename=f"{uuid.uuid4()}.pdf",
            original_name="secret.pdf",
            file_path="/tmp/secret.pdf",
            file_size=512,
            status="ready",
        )
        db_session.add(other_doc)
        await db_session.commit()

        resp = await client.delete(
            f"/api/v1/documents/{other_doc.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
