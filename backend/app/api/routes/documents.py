from __future__ import annotations

import os
from pathlib import Path
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.organization import OrganizationMembership
from app.models.user import User
from app.schemas.document import DocumentList, DocumentRead
from app.workers.tasks import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {"application/pdf", "application/x-pdf"}
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


async def _get_default_org_id(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    stmt = select(OrganizationMembership).where(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.is_default.is_(True),
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()
    return membership.organization_id if membership else None


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID | None = None,
) -> DocumentRead:
    if file.content_type not in ALLOWED_TYPES and not (file.filename or "").endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}.pdf"
    file_path = upload_dir / safe_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    target_org_id = org_id or await _get_default_org_id(current_user.id, db)

    doc = Document(
        owner_id=current_user.id,
        organization_id=target_org_id,
        filename=safe_name,
        original_name=file.filename or safe_name,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=file.content_type or "application/pdf",
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    ingest_document.apply_async(
        args=[str(doc.id), str(file_path)],
        queue="ingestion",
    )

    return DocumentRead.model_validate(doc)


@router.get("/", response_model=DocumentList)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    org_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentList:
    target_org_id = org_id or await _get_default_org_id(current_user.id, db)

    conditions = [Document.owner_id == current_user.id]
    if target_org_id:
        conditions.append(Document.organization_id == target_org_id)

    stmt = (
        select(Document)
        .where(*conditions)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = (await db.execute(stmt)).scalars().all()

    total_stmt = select(Document).where(*conditions)
    total = len((await db.execute(total_stmt)).scalars().all())

    return DocumentList(
        items=[DocumentRead.model_validate(d) for d in docs],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    doc = await _get_owned_doc(document_id, current_user.id, db)
    return DocumentRead.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    doc = await _get_owned_doc(document_id, current_user.id, db)
    try:
        os.remove(doc.file_path)
    except FileNotFoundError:
        pass
    await db.delete(doc)
    await db.commit()


async def _get_owned_doc(doc_id: uuid.UUID, owner_id: uuid.UUID, db: AsyncSession) -> Document:
    stmt = select(Document).where(Document.id == doc_id, Document.owner_id == owner_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
