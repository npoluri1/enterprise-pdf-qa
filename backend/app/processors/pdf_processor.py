"""PDF ingestion: Unstructured.io → structured elements → text."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


class PDFProcessor:
    """
    Uses Unstructured.io (local or cloud) to extract text from PDFs.
    Falls back to pypdf if Unstructured is unavailable.
    """

    async def process(self, file_path: str) -> list[dict[str, Any]]:
        """Return list of {text, page_number, element_type, metadata}."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        if settings.unstructured_api_key:
            return await self._process_cloud(path)
        return await self._process_local(path)

    async def _process_local(self, path: Path) -> list[dict[str, Any]]:
        return await self._process_pypdf(path)

    async def _process_cloud(self, path: Path) -> list[dict[str, Any]]:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    settings.unstructured_api_url,
                    headers={"unstructured-api-key": settings.unstructured_api_key},
                    files={"files": (path.name, f, "application/pdf")},
                    data={"strategy": "hi_res", "include_page_breaks": "true"},
                )
            resp.raise_for_status()
            elements = resp.json()

        results = [
            {
                "text": el.get("text", ""),
                "page_number": el.get("metadata", {}).get("page_number"),
                "element_type": el.get("type", "Unknown"),
                "metadata": el.get("metadata", {}),
            }
            for el in elements
            if el.get("text", "").strip()
        ]
        log.info("pdf_processed_cloud", path=str(path), elements=len(results))
        return results

    async def _process_pypdf(self, path: Path) -> list[dict[str, Any]]:
        import re
        from pypdf import PdfReader

        _ctrl = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

        reader = PdfReader(str(path))
        results = []
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            text = _ctrl.sub('', raw)   # strip null bytes and control chars
            if text.strip():
                results.append(
                    {
                        "text": text,
                        "page_number": i,
                        "element_type": "NarrativeText",
                        "metadata": {"page_number": i},
                    }
                )
        log.info("pdf_processed_pypdf", path=str(path), pages=len(results))
        return results

    def get_page_count(self, file_path: str) -> int:
        from pypdf import PdfReader
        return len(PdfReader(file_path).pages)
