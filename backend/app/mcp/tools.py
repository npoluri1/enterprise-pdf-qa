"""
MCP tool definitions for Claude integration.

These tools let Claude (via Anthropic API tool_use) search documents,
retrieve chunks, and look up metadata – giving Claude grounded, cited answers.
"""
from __future__ import annotations

from typing import Any

DOCUMENT_SEARCH_TOOL = {
    "name": "search_documents",
    "description": (
        "Search across all uploaded PDF documents using semantic + keyword search. "
        "Returns the most relevant text passages with source citations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query or question",
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of document UUIDs to scope the search. Omit to search all.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of passages to return (1-20, default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

DOCUMENT_METADATA_TOOL = {
    "name": "get_document_metadata",
    "description": "Get metadata about a specific document: name, page count, status, upload date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "UUID of the document",
            },
        },
        "required": ["document_id"],
    },
}

LIST_DOCUMENTS_TOOL = {
    "name": "list_documents",
    "description": "List all available documents that can be searched.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

ALL_MCP_TOOLS = [DOCUMENT_SEARCH_TOOL, DOCUMENT_METADATA_TOOL, LIST_DOCUMENTS_TOOL]
