"""Cross-encoder reranker using HuggingFace Transformers."""

from __future__ import annotations

from functools import lru_cache
import math
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> Any:
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(settings.reranker_model, max_length=512)
    log.info("reranker_loaded", model=settings.reranker_model)
    return model


def _sigmoid(x: float) -> float:
    """Normalize a raw logit score to (0, 1).

    Cross-encoder models output unbounded logits (e.g. -3.0 to +3.0).
    Displaying them raw gives nonsensical values like -272%.
    Sigmoid maps them to a meaningful relevance probability:
      -3.0 → 5%   0.0 → 50%   +3.0 → 95%
    """
    return 1.0 / (1.0 + math.exp(-x))


class CrossEncoderReranker:
    """Re-scores (query, passage) pairs using a cross-encoder."""

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = settings.reranker_top_k,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        import asyncio

        model = _load_model()
        pairs = [(query, c["content"]) for c in candidates]

        loop = asyncio.get_running_loop()
        raw_scores = await loop.run_in_executor(
            None, lambda: model.predict(pairs, show_progress_bar=False).tolist()
        )

        for candidate, score in zip(candidates, raw_scores, strict=False):
            # Store sigmoid-normalized score so all consumers get a value in (0, 1)
            candidate["rerank_score"] = _sigmoid(float(score))

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]
