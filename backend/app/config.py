"""Central configuration – loaded once at startup via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_name: str = "Enterprise PDF Q&A"
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "change-me-super-secret-key-at-least-32-chars"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/pdf_qa"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── AI / LLM ─────────────────────────────────────────────
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    primary_llm: Literal["openai", "anthropic"] = "openai"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-6"

    # ── Embeddings ────────────────────────────────────────────
    embedding_provider: Literal["openai", "huggingface"] = "openai"
    openai_embedding_model: str = "text-embedding-3-large"
    hf_embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimension: int = 1536  # must stay ≤ 2000 (pgvector HNSW limit)

    # ── Reranker ──────────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    reranker_top_k: int = 5

    # ── Unstructured ──────────────────────────────────────────
    unstructured_api_key: str = ""
    unstructured_api_url: str = "https://api.unstructured.io/general/v0/general"

    # ── RAG ───────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 20
    final_top_k: int = 5
    hybrid_alpha: float = 0.7   # 1.0 = pure dense, 0.0 = pure BM25

    # ── Storage ───────────────────────────────────────────────
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50

    # ── Observability ─────────────────────────────────────────
    log_level: str = "INFO"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "enterprise-pdf-qa"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
