"""Semantic-aware text chunker using LangChain splitters."""

from __future__ import annotations

import re
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import settings

# PostgreSQL UTF-8 rejects null bytes and most C0 control characters.
# Tab (\x09), newline (\x0a), and carriage-return (\x0d) are kept as valid text.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str) -> str:
    """Strip bytes that PostgreSQL's UTF-8 encoder rejects."""
    return _CONTROL_RE.sub("", text)


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            add_start_index=True,
        )

    def chunk_elements(self, elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Split parsed PDF elements into overlapping text chunks."""
        chunks: list[dict[str, Any]] = []
        index = 0

        for element in elements:
            text = _clean(element.get("text", "").strip())
            if not text:
                continue

            splits = self._splitter.split_text(text)
            for split in splits:
                cleaned = _clean(split.strip())
                if not cleaned:
                    continue
                chunks.append(
                    {
                        "content": cleaned,
                        "chunk_index": index,
                        "page_number": element.get("page_number"),
                        "element_type": element.get("element_type"),
                        "token_count": self._estimate_tokens(cleaned),
                        "metadata": element.get("metadata", {}),
                    }
                )
                index += 1

        return chunks

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)
