"""Shared pytest fixtures for all test modules."""
from __future__ import annotations

import asyncio
import io
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.document import Chunk, Document
from app.models.user import User

# ── Test database ─────────────────────────────────────────────────────────────

TEST_DATABASE_URL = settings.database_url.replace(
    "/pdf_qa", "/pdf_qa_test"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── User / auth fixtures ──────────────────────────────────────────────────────

@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


# ── Document fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
async def test_document(db_session: AsyncSession, test_user: User) -> Document:
    doc = Document(
        owner_id=test_user.id,
        filename=f"{uuid.uuid4()}.pdf",
        original_name="test.pdf",
        file_path="/tmp/test.pdf",
        file_size=1024,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def test_chunks(db_session: AsyncSession, test_document: Document) -> list[Chunk]:
    chunks = [
        Chunk(
            document_id=test_document.id,
            content=f"Test chunk content number {i} about artificial intelligence.",
            embedding=[0.1] * settings.embedding_dimension,
            chunk_index=i,
            page_number=i + 1,
        )
        for i in range(3)
    ]
    db_session.add_all(chunks)
    await db_session.commit()
    return chunks


# ── Minimal PDF fixture ───────────────────────────────────────────────────────

@pytest.fixture
def minimal_pdf() -> bytes:
    """A minimal valid-enough PDF for upload testing (real PDF header)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n0\n%%EOF"
    )
