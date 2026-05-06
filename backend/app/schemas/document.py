from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    file_size: int
    status: str
    page_count: int | None
    chunk_count: int | None
    meta: dict[str, Any] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int


class ChunkRead(BaseModel):
    id: uuid.UUID
    chunk_index: int
    page_number: int | None
    content: str
    token_count: int | None
    model_config = {"from_attributes": True}
