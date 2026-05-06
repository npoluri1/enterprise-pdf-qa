from __future__ import annotations

from typing import Any
import uuid

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int | None
    content: str
    relevance_score: float


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    document_ids: list[uuid.UUID] | None = Field(
        default=None, description="Scope to specific docs; None = all"
    )
    top_k: int = Field(default=5, ge=1, le=20)
    use_reranker: bool = True
    stream: bool = False


class QuestionResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    model_used: str
    tokens_used: int | None
    confidence: float | None
    meta: dict[str, Any] | None = None


class StreamChunk(BaseModel):
    type: str  # "token" | "citation" | "done" | "error"
    content: str | None = None
    citations: list[Citation] | None = None
    error: str | None = None
