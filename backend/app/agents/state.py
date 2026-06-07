"""Shared state types for LangGraph multi-agent graph."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
import uuid

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # User inputs
    question: str
    document_ids: list[uuid.UUID] | None
    user_id: uuid.UUID
    organization_id: uuid.UUID | None

    # Retrieved evidence
    retrieved_chunks: list[dict[str, Any]]
    expanded_queries: list[str]

    # Agent outputs
    routed_to: str  # which specialist handled this
    answer: str
    citations: list[dict[str, Any]]
    confidence: float | None

    # Control flow
    error: str | None
    messages: Annotated[list[Any], add_messages]  # full message history
    iteration: int


class DocumentIngestionState(TypedDict):
    document_id: uuid.UUID
    file_path: str
    status: str  # pending | processing | ready | failed
    elements: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
    embeddings_generated: bool
    error: str | None
    messages: Annotated[list[Any], add_messages]
