"""FastAPI application entry-point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.api.routes import auth, documents, qa
from app.config import settings
from app.database import init_db

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Enterprise PDF Q&A – RAG + Multi-Agent + MCP",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Prometheus metrics ───────────────────────────────────
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # ── Routers ──────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(documents.router, prefix=api_prefix)
    app.include_router(qa.router, prefix=api_prefix)

    # ── Startup ──────────────────────────────────────────────
    @app.on_event("startup")
    async def startup() -> None:
        log.info("startup", env=settings.app_env)
        await init_db()
        # Pre-warm embedding model
        from app.rag.embeddings import get_embedder

        get_embedder()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        log.info("shutdown")

    # ── Health check ──────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
