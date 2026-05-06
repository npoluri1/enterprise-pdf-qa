# Enterprise PDF Q&A — Complete Codebase Guide

> **Scope**: Full line-by-line architecture, every code flow, and sequence diagrams from UI to database.
> **Stack**: FastAPI · LangGraph · pgvector · Celery · Redis · React 18 · TypeScript · TailwindCSS · Docker Compose

---

## Table of Contents

1. [Project Layout](#1-project-layout)
2. [Infrastructure — 8 Docker Containers](#2-infrastructure--8-docker-containers)
3. [Configuration (`config.py`)](#3-configuration-configpy)
4. [Database Layer](#4-database-layer)
5. [Data Models](#5-data-models)
6. [Security — JWT + bcrypt](#6-security--jwt--bcrypt)
7. [FastAPI Application Bootstrap (`main.py`)](#7-fastapi-application-bootstrap-mainpy)
8. [API Routes](#8-api-routes)
9. [Celery Worker — Async Ingestion](#9-celery-worker--async-ingestion)
10. [LangGraph Ingestion Pipeline](#10-langgraph-ingestion-pipeline)
11. [RAG Layer — Embeddings, Retrieval, Reranking](#11-rag-layer--embeddings-retrieval-reranking)
12. [LangGraph Multi-Agent Q&A Graph](#12-langgraph-multi-agent-qa-graph)
13. [MCP Server — Claude Tool-Use Loop](#13-mcp-server--claude-tool-use-loop)
14. [Frontend Architecture](#14-frontend-architecture)
15. [Complete Sequence Flows](#15-complete-sequence-flows)
    - [Flow 1: User Registration & Login](#flow-1-user-registration--login)
    - [Flow 2: PDF Upload → Ingestion](#flow-2-pdf-upload--ingestion)
    - [Flow 3: Q&A (LangGraph Mode)](#flow-3-qa-langgraph-mode)
    - [Flow 4: Q&A (MCP Mode)](#flow-4-qa-mcp-mode)
    - [Flow 5: Streaming Answer (SSE)](#flow-5-streaming-answer-sse)
16. [Where Files Live — Quick Reference](#16-where-files-live--quick-reference)

---

## 1. Project Layout

```
enterprise-pdf-qa/
│
├── backend/                     # Python FastAPI service
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + startup hooks
│   │   ├── config.py            # All settings (pydantic-settings, .env)
│   │   ├── database.py          # SQLAlchemy async engine + session factory
│   │   │
│   │   ├── models/              # SQLAlchemy ORM table definitions
│   │   │   ├── user.py          # User table
│   │   │   └── document.py      # Document + Chunk tables (pgvector)
│   │   │
│   │   ├── schemas/             # Pydantic v2 request/response schemas
│   │   │   ├── user.py          # UserCreate, UserRead, Token
│   │   │   ├── document.py      # DocumentRead, DocumentList
│   │   │   └── qa.py            # QuestionRequest, QuestionResponse, Citation
│   │   │
│   │   ├── core/
│   │   │   ├── security.py      # bcrypt hash/verify + JWT encode/decode
│   │   │   └── dependencies.py  # FastAPI Depends() — get_current_user
│   │   │
│   │   ├── api/routes/
│   │   │   ├── auth.py          # POST /auth/register|login  GET /auth/me
│   │   │   ├── documents.py     # POST /documents/upload  GET|DELETE /documents/
│   │   │   └── qa.py            # POST /qa/ask|ask/mcp|ask/stream
│   │   │
│   │   ├── agents/
│   │   │   ├── state.py         # AgentState + DocumentIngestionState TypedDicts
│   │   │   └── graph.py         # build_qa_graph() + build_ingestion_graph()
│   │   │
│   │   ├── rag/
│   │   │   ├── embeddings.py    # get_embedder() — OpenAI or HuggingFace
│   │   │   ├── retriever.py     # HybridRetriever — dense + BM25 + RRF
│   │   │   ├── reranker.py      # CrossEncoderReranker
│   │   │   └── pipeline.py      # RAGPipeline — orchestrates all RAG steps
│   │   │
│   │   ├── processors/
│   │   │   ├── pdf_processor.py # PDFProcessor — calls Unstructured API
│   │   │   └── chunker.py       # DocumentChunker — sliding window
│   │   │
│   │   ├── mcp/
│   │   │   ├── tools.py         # ALL_MCP_TOOLS definitions for Anthropic SDK
│   │   │   └── server.py        # MCPDocumentServer — Claude agentic loop
│   │   │
│   │   └── workers/
│   │       ├── celery_app.py    # Celery app instance + beat schedule
│   │       └── tasks.py         # ingest_document task + cleanup_failed_documents
│   │
│   ├── alembic/                 # DB migrations
│   │   ├── env.py
│   │   └── versions/001_initial.py
│   ├── tests/                   # pytest test suite
│   ├── requirements.txt
│   ├── pyproject.toml           # ruff + mypy config
│   └── Dockerfile
│
├── frontend/                    # React 18 + TypeScript SPA
│   ├── src/
│   │   ├── main.tsx             # React DOM entry-point
│   │   ├── App.tsx              # Router + QueryClient + PrivateRoute
│   │   ├── index.css            # Tailwind base imports
│   │   │
│   │   ├── api/
│   │   │   └── client.ts        # Axios instance + authApi + docsApi + qaApi
│   │   │
│   │   ├── store/
│   │   │   └── authStore.ts     # Zustand auth state (token + user)
│   │   │
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx    # Register/Login form with toggle
│   │   │   └── DashboardPage.tsx# Main UI: sidebar + chat area + mode selector
│   │   │
│   │   ├── components/
│   │   │   ├── PDFUpload.tsx    # Drag-and-drop upload with progress
│   │   │   ├── DocumentList.tsx # Checkbox list with status badges + delete
│   │   │   ├── ChatInterface.tsx# Chat UI with streaming + citations
│   │   │   └── CitationPanel.tsx# Collapsible source citation cards
│   │   │
│   │   └── hooks/
│   │       ├── useAuth.ts       # register/login mutations
│   │       ├── useDocuments.ts  # upload/delete mutations + list query
│   │       └── useQA.ts         # ask/askMcp/stream mutations
│   │
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf               # Dev: proxy /api/* → backend, /* → frontend
│   └── nginx.prod.conf          # Prod: SSL termination + same proxy rules
│
├── scripts/
│   └── init_db.sql              # Postgres extensions: pgvector, pg_trgm, uuid-ossp
│
├── docker-compose.yml           # 8-container dev stack
├── docker-compose.prod.yml      # Production overrides (replicas, resource limits)
├── Makefile                     # Developer shortcuts
├── .env.example                 # Template — copy to .env
└── CLAUDE.md                    # AI assistant instructions for this project
```

---

## 2. Infrastructure — 8 Docker Containers

```
┌─────────────────────────────────────────────────────┐
│                    nginx : 80                        │
│  /api/*  ─────────────────────► backend : 8000       │
│  /*      ─────────────────────► frontend : 3000      │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────┐    ┌──────────────────────────┐
│  backend : 8000      │    │  worker (Celery)          │
│  FastAPI             │───►│  ingestion queue          │
│  uvicorn             │    │  asyncio.run() per task   │
└──────────────────────┘    └──────────────────────────┘
         │                           │
         │                           │
         ▼                           ▼
┌──────────────────────┐    ┌──────────────────────────┐
│  postgres : 5432     │    │  redis : 6379             │
│  pgvector extension  │    │  db0: app cache           │
│  pg_trgm extension   │    │  db1: Celery broker       │
│  uuid-ossp           │    │  db2: Celery results      │
└──────────────────────┘    └──────────────────────────┘
                                      │
                             ┌────────▼─────────┐
                             │  flower : 5555    │
                             │  Celery monitor   │
                             └───────────────────┘

Observability (separate compose profile):
  prometheus : 9090  ← scrapes /metrics on backend
```

**Networking rules (docker-compose internal DNS)**

| From     | To         | Hostname  |
|----------|------------|-----------|
| backend  | postgres   | `postgres` |
| backend  | redis      | `redis`    |
| worker   | postgres   | `postgres` |
| worker   | redis      | `redis`    |
| nginx    | backend    | `backend`  |
| nginx    | frontend   | `frontend` |

> Never use `localhost` inside containers — the hostname is the service name.

---

## 3. Configuration (`config.py`)

**File**: `backend/app/config.py`

All runtime settings live in one `Settings` class powered by **pydantic-settings**. It reads from `.env` at startup and is cached once via `@lru_cache`.

```python
# How it's imported everywhere in the app:
from app.config import settings
```

### Key Settings Groups

| Group | Key vars | Notes |
|-------|----------|-------|
| App | `SECRET_KEY`, `APP_ENV`, `ACCESS_TOKEN_EXPIRE_MINUTES` | SECRET_KEY must be 32+ chars |
| Database | `DATABASE_URL` | `postgresql+asyncpg://...` |
| Redis / Celery | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Three separate Redis dbs |
| LLM | `PRIMARY_LLM`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_MODEL`, `ANTHROPIC_MODEL` | Switch between OpenAI and Anthropic |
| Embeddings | `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSION` | **Must be ≤ 2000** (pgvector HNSW limit). Use 1536, never 3072 |
| RAG | `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_TOP_K`, `FINAL_TOP_K`, `HYBRID_ALPHA` | `hybrid_alpha=0.7` → 70% dense, 30% BM25 |
| Storage | `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB` | Files stored at `/app/uploads/` outside web root |
| Observability | `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY` | LangSmith tracing |

### `allowed_origins` parsing trick
```python
@field_validator("allowed_origins", mode="before")
@classmethod
def parse_origins(cls, v: str | list) -> list[str]:
    if isinstance(v, str):
        return [o.strip() for o in v.split(",")]
    return v
```
In `.env` you can write either `ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173`
or a JSON array `["http://localhost:3000"]`.

---

## 4. Database Layer

**File**: `backend/app/database.py`

```python
engine = create_async_engine(settings.database_url, pool_pre_ping=True, ...)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- All DB sessions are `AsyncSession` from SQLAlchemy 2.0.
- `expire_on_commit=False` keeps ORM objects usable after commit without re-fetching.
- `pool_pre_ping=True` verifies connections before use (avoids stale connection errors after container restarts).
- **Alembic** handles schema migrations. `make migrate` runs `alembic upgrade head`.

---

## 5. Data Models

### `users` table — `backend/app/models/user.py`

```
id            UUID PK
email         VARCHAR(255) UNIQUE NOT NULL
hashed_password VARCHAR(512) NOT NULL        ← bcrypt hash
full_name     VARCHAR(255) nullable
is_active     BOOLEAN default true
created_at    TIMESTAMPTZ server_default now()
updated_at    TIMESTAMPTZ
```

**Relationships**: `User.documents` → list of `Document` (one-to-many, cascade delete)

### `documents` table — `backend/app/models/document.py`

```
id            UUID PK
owner_id      UUID FK → users.id (CASCADE DELETE)
filename      VARCHAR(512)   ← UUID-named file on disk e.g. "a1b2c3.pdf"
original_name VARCHAR(512)   ← user's original filename
file_path     VARCHAR(1024)  ← absolute path on the worker/backend volume
file_size     INTEGER        ← bytes
mime_type     VARCHAR(128)   ← "application/pdf"
status        VARCHAR(32)    ← pending | processing | ready | failed
page_count    INTEGER nullable
chunk_count   INTEGER nullable
meta          JSONB nullable ← extra metadata
error_message TEXT nullable  ← populated on failure
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
```

**Relationships**: `Document.chunks` → list of `Chunk` (cascade delete)

### `chunks` table — `backend/app/models/document.py`

```
id            UUID PK
document_id   UUID FK → documents.id (CASCADE DELETE)
content       TEXT NOT NULL         ← raw text of this chunk
embedding     VECTOR(1536)          ← pgvector column, dimension from settings
chunk_index   INTEGER NOT NULL      ← 0-based position in document
page_number   INTEGER nullable      ← source page
token_count   INTEGER nullable
meta          JSONB nullable
created_at    TIMESTAMPTZ
```

**Index**: HNSW cosine similarity index for fast ANN search
```sql
CREATE INDEX ix_chunks_embedding_hnsw ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
- `m=16`: max edges per node in HNSW graph (controls recall vs. build time)
- `ef_construction=64`: build-time search depth

---

## 6. Security — JWT + bcrypt

**File**: `backend/app/core/security.py`

### Password Hashing
```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```
Uses `bcrypt` directly (v4.2.1+) — **not** `passlib`. Default cost factor ~12.

### JWT Tokens
```python
ALGORITHM = "HS256"

def create_access_token(subject: uuid.UUID, ...) -> str:
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

def decode_access_token(token: str) -> uuid.UUID:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    return uuid.UUID(payload["sub"])
```

### Auth Dependency — `backend/app/core/dependencies.py`
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(token)   # raises JWTError on invalid
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Unauthorized")
    return user
```
Every protected route adds `current_user: User = Depends(get_current_user)`.

---

## 7. FastAPI Application Bootstrap (`main.py`)

**File**: `backend/app/main.py`

```python
def create_app() -> FastAPI:
    app = FastAPI(title=..., docs_url="/docs", ...)

    # 1. CORS middleware — uses settings.allowed_origins
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, ...)

    # 2. Prometheus metrics — auto-instruments all routes, exposes /metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # 3. Register routers under /api/v1
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(qa.router, prefix="/api/v1")

    # 4. Startup: init DB tables + pre-warm embedding model
    @app.on_event("startup")
    async def startup():
        await init_db()
        get_embedder()   # loads model into memory once

    # 5. Health check — no auth required
    @app.get("/health")
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app

app = create_app()
```

`uvicorn` runs `app.main:app`. The `app` object is the ASGI application.

---

## 8. API Routes

### Auth Routes — `/api/v1/auth/`

**File**: `backend/app/api/routes/auth.py`

| Method | Path | Auth? | What it does |
|--------|------|-------|-------------|
| POST | `/auth/register` | No | Creates User, hashes password, returns UserRead |
| POST | `/auth/login` | No | Accepts `x-www-form-urlencoded`, verifies password, returns JWT |
| GET | `/auth/me` | Yes | Returns current user profile |

**Login requires form-encoded body** (OAuth2 standard):
```
Content-Type: application/x-www-form-urlencoded
username=user@example.com&password=secret
```
This is why the frontend uses `URLSearchParams` instead of JSON.

### Document Routes — `/api/v1/documents/`

**File**: `backend/app/api/routes/documents.py`

| Method | Path | Auth? | What it does |
|--------|------|-------|-------------|
| POST | `/documents/upload` | Yes | Validates PDF, saves to disk, creates DB record, dispatches Celery task |
| GET | `/documents/` | Yes | Returns paginated list of own documents |
| GET | `/documents/{id}` | Yes | Returns single document |
| DELETE | `/documents/{id}` | Yes | Deletes file from disk + DB record |

**Upload flow (inside the route)**:
1. Check MIME type: `application/pdf` or filename ends with `.pdf`
2. Read full file bytes, check size against `MAX_UPLOAD_SIZE_MB`
3. Save to disk as `{uuid4}.pdf` inside `settings.upload_dir`
4. Insert `Document` row with `status="pending"`
5. Call `ingest_document.apply_async(args=[doc_id, file_path], queue="ingestion")`
6. Return `DocumentRead` immediately — ingestion is async

### Q&A Routes — `/api/v1/qa/`

**File**: `backend/app/api/routes/qa.py`

| Method | Path | Auth? | What it does |
|--------|------|-------|-------------|
| POST | `/qa/ask` | Yes | LangGraph multi-agent RAG answer |
| POST | `/qa/ask/mcp` | Yes | Claude + MCP tool-use agentic loop |
| POST | `/qa/ask/stream` | Yes | SSE streaming tokens via RAGPipeline |

**Request schema** (`QuestionRequest`):
```python
class QuestionRequest(BaseModel):
    question: str
    document_ids: list[uuid.UUID] | None = None  # None = search all
    top_k: int = 5
    use_reranker: bool = True
    stream: bool = False
```

---

## 9. Celery Worker — Async Ingestion

**Files**: `backend/app/workers/celery_app.py`, `backend/app/workers/tasks.py`

### Why Celery?
PDF ingestion is slow (parse → chunk → embed = 10–120 seconds). The upload API returns immediately and Celery processes it in the background, allowing the user to continue interacting with the UI.

### Task Definition
```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_document(self, document_id: str, file_path: str) -> None:
    try:
        asyncio.run(_ingest(uuid.UUID(document_id), file_path))
    except Exception as exc:
        raise self.retry(exc=exc)  # auto-retry up to 3 times
```

`asyncio.run()` is intentional — Celery workers are synchronous, but the ingestion pipeline is async. Each task call creates a fresh event loop.

### `_ingest()` async function
```python
async def _ingest(document_id, file_path):
    # 1. Create FRESH engine — each asyncio.run() creates a new loop;
    #    existing pool connections are bound to the old loop.
    engine = create_async_engine(settings.database_url, ...)
    SessionFactory = async_sessionmaker(bind=engine, ...)

    # 2. Mark document as "processing"
    async with SessionFactory() as db:
        await _set_status(db, document_id, "processing")

    # 3. Run the LangGraph ingestion graph
    graph = build_ingestion_graph(settings.database_url)
    await graph.ainvoke({
        "document_id": document_id,
        "file_path": file_path,
        "status": "processing",
        ...
    })
```

### Cleanup Beat Task
```python
@celery_app.task
def cleanup_failed_documents():
    """Documents stuck in 'processing' > 2 hours → mark as failed."""
```
Scheduled via Celery Beat (configured in `celery_app.py`).

---

## 10. LangGraph Ingestion Pipeline

**File**: `backend/app/agents/graph.py` — `build_ingestion_graph()`

This is a separate LangGraph graph used exclusively for ingesting PDFs. It runs inside the Celery worker.

```
State: DocumentIngestionState
  document_id, file_path, status, elements, chunks, embeddings_generated, error

Graph:
  [parse] ──(ok)──► [chunk] ──► [embed] ──► END
     └──(fail)──► [failed] ──► END
```

### Node: `parse_node`
```python
async def parse_node(state):
    proc = PDFProcessor()
    elements = await proc.process(state["file_path"])
    # PDFProcessor calls Unstructured API or falls back to local pypdf
    # Returns list of {"type": "NarrativeText", "content": "...", "page_number": 1, ...}
    return {"elements": elements, "status": "parsed"}
```

### Node: `chunk_node`
```python
async def chunk_node(state):
    chunker = DocumentChunker()
    chunks = chunker.chunk_elements(state["elements"])
    # Sliding window: chunk_size=512 tokens, overlap=64
    # Returns list of {"content": "...", "chunk_index": 0, "page_number": 1, "token_count": 480}
    return {"chunks": chunks, "status": "chunked"}
```

### Node: `embed_node`
```python
async def embed_node(state):
    embedder = get_embedder()
    texts = [c["content"] for c in chunks]

    # Batch embed in groups of 100
    all_vectors = []
    for i in range(0, len(texts), 100):
        vecs = await embedder.embed(texts[i:i+100])
        all_vectors.extend(vecs)

    # Write Chunk rows to DB with embedding vectors
    async with SessionFactory() as session:
        chunk_objects = [Chunk(document_id=..., embedding=vector, ...) for ...]
        session.add_all(chunk_objects)
        doc.status = "ready"
        await session.commit()
```

**Why each node creates its own DB session**: LangGraph runs nodes with `asyncio.create_task()`, which resets SQLAlchemy's greenlet context. Reusing a session from the parent task raises `MissingGreenletError`.

### Node: `failed_node`
On any error, marks `Document.status = "failed"` with an error message.

---

## 11. RAG Layer — Embeddings, Retrieval, Reranking

### Embeddings — `backend/app/rag/embeddings.py`

```python
def get_embedder():
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder(model=settings.openai_embedding_model)
    return HuggingFaceEmbedder(model=settings.hf_embedding_model)
```

- **OpenAI**: `text-embedding-3-large` → 1536 dims (default)
- **HuggingFace**: `BAAI/bge-large-en-v1.5` → 1024 dims (local, no API cost)

The embedder is pre-warmed at startup (`get_embedder()` in `startup()`) so the first request doesn't pay the cold-start cost.

### Hybrid Retriever — `backend/app/rag/retriever.py`

`HybridRetriever.retrieve(query, document_ids, top_k)` runs **three steps**:

**Step 1 — Dense Search (pgvector)**
```sql
SELECT c.id, c.document_id, c.content, c.page_number, d.original_name,
       1 - (c.embedding <=> '{query_vector}'::vector) AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE c.embedding IS NOT NULL AND d.status = 'ready'
  [AND c.document_id IN (...)]    -- optional scope
ORDER BY c.embedding <=> '{query_vector}'::vector   -- cosine distance ASC
LIMIT :top_k
```
Uses the HNSW index → approximate nearest neighbour in O(log n).

**Step 2 — Sparse Search (BM25)**
```python
# Load all chunks for candidate documents into memory
rows = await db.execute(select(Chunk).where(...))
tokenized = [r.content.lower().split() for r in rows]
bm25 = BM25Okapi(tokenized)
scores = bm25.get_scores(query.lower().split())
# Return top_k sorted by BM25 score
```
BM25 is keyword-exact — catches acronyms and proper nouns that embeddings miss.

**Step 3 — RRF Fusion**
```python
# Reciprocal Rank Fusion: score = Σ 1/(k + rank)  where k=60
for rank, item in enumerate(dense_results):
    scores[item_id] += 1 / (60 + rank + 1)
for rank, item in enumerate(sparse_results):
    scores[item_id] += 1 / (60 + rank + 1)
# Re-sort by fused score, return top_k
```
RRF is rank-based, so it handles the different score scales of dense and sparse.

### Cross-Encoder Reranker — `backend/app/rag/reranker.py`

```python
class CrossEncoderReranker:
    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")

    async def rerank(self, query, candidates, top_k):
        pairs = [[query, c["content"]] for c in candidates]
        scores = self.model.predict(pairs)  # (query, passage) relevance scores
        ranked = sorted(zip(scores, candidates), reverse=True)
        return [c for _, c in ranked[:top_k]]
```
The cross-encoder scores each (query, passage) pair together — more accurate than bi-encoder cosine similarity but slower. Run only on the top candidates from retrieval.

### RAG Pipeline — `backend/app/rag/pipeline.py`

`RAGPipeline.run()` orchestrates all steps for the streaming endpoint and direct calls:

```
question
  → _expand_query()          # LLM generates 3 diverse sub-queries
  → for each query: retrieve  # dense + sparse + RRF
  → deduplicate               # seen_ids set
  → reranker.rerank()         # cross-encoder on all candidates
  → _build_context()          # numbered passages with source labels
  → LLM (QA_PROMPT)          # generates answer with inline citations
  → _build_citations()        # Citation objects for response
```

---

## 12. LangGraph Multi-Agent Q&A Graph

**File**: `backend/app/agents/graph.py` — `build_qa_graph()`

### State: `AgentState`
```python
class AgentState(TypedDict):
    question: str
    document_ids: list[uuid.UUID] | None
    user_id: uuid.UUID
    retrieved_chunks: list[dict]
    expanded_queries: list[str]
    routed_to: str          # "retrieval" or "fallback"
    answer: str
    citations: list[dict]
    confidence: float | None
    error: str | None
    messages: Annotated[list, add_messages]  # full LLM message history
    iteration: int
```

### Graph Structure
```
                    ┌─────────────┐
                    │  SUPERVISOR │  ← decides: retrieval or fallback
                    └──────┬──────┘
              ┌────────────┴────────────┐
           "expand"                 "fallback"
              │                        │
      ┌───────▼───────┐       ┌────────▼───────┐
      │    EXPAND     │       │    FALLBACK    │
      │  3 sub-queries│       │  out-of-scope  │
      └───────┬───────┘       └────────┬───────┘
              │                        │
      ┌───────▼───────┐               END
      │   RETRIEVE    │
      │ dense+BM25+RRF│
      │ + cross-encoder│
      └───────┬───────┘
              │
      ┌───────▼───────┐
      │  SYNTHESIZE   │
      │  cited answer │
      └───────┬───────┘
              │
      ┌───────▼───────┐
      │   EVALUATE    │
      │  confidence   │
      └───────┬───────┘
              │
             END
```

### Each Agent Node in Detail

**`supervisor_node`** (temperature=0.0)
- Prompt: "Reply ONLY with 'retrieval' or 'fallback'. When in doubt, always choose retrieval."
- Sets `state["routed_to"]`

**`query_expansion_node`** (temperature=0.3)
- Prompt: "Generate 3 diverse search queries, one per line."
- Sets `state["expanded_queries"]` — used by retrieval to improve recall

**`retrieval_node`**
- Creates its own `AsyncSessionLocal()` session (avoids MissingGreenlet)
- Runs all original + expanded queries through `HybridRetriever`
- Deduplicates by chunk id
- Reranks via `CrossEncoderReranker`
- Sets `state["retrieved_chunks"]`

**`synthesis_node`** (temperature=0.1)
- Formats chunks into numbered context: `[1] Source: doc.pdf, Page 3\n{content}`
- Prompt: "Answer using ONLY the context. Cite sources as [Doc: <name>, Page: <n>]."
- Sets `state["answer"]` + `state["citations"]`

**`eval_node`** (temperature=0.0)
- Prompt: "Rate answer confidence 0.0–1.0. Reply with ONLY a float."
- Sets `state["confidence"]`

**`fallback_node`**
- Returns a static "out-of-scope" message with `confidence=0.0`

---

## 13. MCP Server — Claude Tool-Use Loop

**Files**: `backend/app/mcp/tools.py`, `backend/app/mcp/server.py`

### What MCP Mode Does Differently
Instead of a pre-defined pipeline, Claude itself decides **when and how** to search. The `MCPDocumentServer` runs a conversation loop where Claude calls tools until it has enough information to answer.

### Available Tools (defined in `tools.py`)

| Tool | Input | What it does |
|------|-------|-------------|
| `search_documents` | `query`, `document_ids?`, `top_k?` | Hybrid retrieval + cross-encoder rerank |
| `get_document_metadata` | `document_id` | Returns page count, chunk count, status |
| `list_documents` | (none) | Lists all ready documents |

### Agent Loop (`MCPDocumentServer.answer()`)
```python
messages = [{"role": "user", "content": question}]
while turns < MAX_AGENT_TURNS:   # MAX = 6
    resp = await client.messages.create(
        model=settings.anthropic_model,
        system="You are an expert document analyst...",
        tools=ALL_MCP_TOOLS,
        messages=messages,
    )

    if resp.stop_reason == "end_turn":
        # Claude finished — extract text answer
        return answer_text, citations

    if resp.stop_reason == "tool_use":
        # Execute each tool Claude requested
        for block in resp.content:
            if block.type == "tool_use":
                result, new_citations = await _execute_tool(block.name, block.input, ...)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        # Feed tool results back to Claude
        messages.append({"role": "user", "content": tool_results})
```

This loop allows Claude to:
1. Call `list_documents` to see what's available
2. Call `search_documents` with different queries
3. Call `get_document_metadata` to verify sources
4. Keep refining until confident, then produce a final answer

---

## 14. Frontend Architecture

### Entry Point — `src/main.tsx`
```tsx
ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
```

### App Shell — `src/App.tsx`
```tsx
<QueryClientProvider client={queryClient}>     // TanStack Query cache
  <BrowserRouter>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={
        <PrivateRoute>      // redirects to /login if no token
          <DashboardPage />
        </PrivateRoute>
      } />
      <Route path="*" element={<Navigate to="/dashboard" />} />
    </Routes>
  </BrowserRouter>
  <Toaster position="top-right" />
</QueryClientProvider>
```

`PrivateRoute` reads `useAuthStore().token` — if null, redirects to `/login`.

### State Management

**Zustand (`authStore.ts`)** — client-only, persisted to `localStorage`:
```typescript
{ token, user, setToken(), setUser(), logout() }
```
`persist()` middleware serializes state to `localStorage['auth-storage']`.

**TanStack Query** — all server state (documents list, Q&A results):
```typescript
// In DashboardPage:
const { data: docsData } = useQuery({
    queryKey: ['documents'],
    queryFn: () => docsApi.list(),
    refetchInterval: 5000,   // polls every 5s for ingestion status updates
})
```

### API Client — `src/api/client.ts`
```typescript
const api = axios.create({ baseURL: `${VITE_API_URL}/api/v1` })

// Interceptor: attach JWT on every request
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// Interceptor: 401 → clear auth + redirect to /login
api.interceptors.response.use(res => res, err => {
    if (err.response?.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
    }
    return Promise.reject(err)
})
```

### Page Components

**`LoginPage.tsx`**
- Toggle between Register and Login forms
- Register: `authApi.register(email, password, name)` → on success auto-login
- Login: `authApi.login(email, password)` → stores token in `authStore` + fetches `/auth/me`

**`DashboardPage.tsx`**
- Left sidebar: `PDFUpload` + `DocumentList`
- Mode selector: `LangGraph Multi-Agent` | `Claude + MCP`
- Main area: `ChatInterface`
- Polls document list every 5s to show live ingestion status

### UI Components

**`PDFUpload.tsx`**
- Drag-and-drop + click-to-browse
- Calls `docsApi.upload(file)` — does NOT set Content-Type (lets Axios set multipart boundary automatically)
- Shows upload progress bar

**`DocumentList.tsx`**
- Renders documents as checkboxes with status badge: `pending` / `processing` / `ready` / `failed`
- Selected document IDs are passed to `ChatInterface` as scope
- Delete button calls `docsApi.delete(id)`

**`ChatInterface.tsx`**
- Chat bubble UI (user right, assistant left)
- Calls `qaApi.ask()` or `qaApi.askMcp()` based on mode prop
- Renders markdown in assistant responses via `react-markdown` + `remark-gfm`
- Shows `ConfidenceBadge` with tooltip (green/yellow/red based on score)
- Shows `CitationPanel` for source citations
- On 503 errors: shows error inline (not toast) because detail text is too long for a toast

**`CitationPanel.tsx`**
- Collapsible list of source citations
- Each card shows: document name, page number, relevance score, content excerpt

---

## 15. Complete Sequence Flows

### Flow 1: User Registration & Login

```
Browser                    nginx                  FastAPI backend              PostgreSQL
   │                         │                          │                           │
   │── POST /api/v1/auth/register ──────────────────────►│                           │
   │   {email, password, full_name}                      │                           │
   │                                                     │── SELECT user by email ──►│
   │                                                     │◄─ None (not found) ───────│
   │                                                     │── hash_password(pw) ──────┤ (bcrypt)
   │                                                     │── INSERT user ────────────►│
   │                                                     │◄─ User row ───────────────│
   │◄── 201 {id, email, full_name, is_active} ───────────│                           │
   │                                                     │                           │
   │── POST /api/v1/auth/login ──────────────────────────►│                           │
   │   username=email&password=pw  (form-encoded)        │                           │
   │                                                     │── SELECT user by email ──►│
   │                                                     │◄─ User row ───────────────│
   │                                                     │── verify_password() ──────┤ (bcrypt)
   │                                                     │── create_access_token() ──┤ (JWT HS256)
   │◄── 200 {access_token: "eyJ..."} ────────────────────│                           │
   │                                                     │                           │
   │ [Frontend stores token in localStorage + Zustand]   │                           │
```

### Flow 2: PDF Upload → Ingestion

```
Browser         nginx        FastAPI /documents/upload    Celery Worker         PostgreSQL    LangGraph
   │               │                    │                       │                    │              │
   │─ POST /upload ►│──────────────────►│                       │                    │              │
   │  multipart/form-data               │                       │                    │              │
   │  + Bearer token                    │                       │                    │              │
   │                                    │─ validate MIME ────────┤                    │              │
   │                                    │─ check size ───────────┤                    │              │
   │                                    │─ write to disk ────────────────────────────┤              │
   │                                    │  /app/uploads/{uuid}.pdf                   │              │
   │                                    │─ INSERT document ──────────────────────────►│              │
   │                                    │  status="pending"                           │              │
   │◄ 201 {id, status:"pending"} ───────│                       │                    │              │
   │                                    │                       │                    │              │
   │                                    │─ ingest_document.apply_async() ────────────►│              │
   │                                    │  (Celery task dispatched to Redis queue)    │              │
   │                                    │                       │                    │              │
   │                                    │               [Worker picks up task]        │              │
   │                                    │                       │── UPDATE status ───►│              │
   │                                    │                       │   "processing"      │              │
   │                                    │                       │                    │              │
   │                                    │                       │── build_ingestion_graph() ─────────►│
   │                                    │                       │                    │              │
   │                                    │                       │          [parse_node]             │
   │                                    │                       │          PDFProcessor.process()   │
   │                                    │                       │          → Unstructured API       │
   │                                    │                       │          → list of elements       │
   │                                    │                       │                    │              │
   │                                    │                       │          [chunk_node]             │
   │                                    │                       │          sliding window 512/64    │
   │                                    │                       │          → list of chunks         │
   │                                    │                       │                    │              │
   │                                    │                       │          [embed_node]             │
   │                                    │                       │          embed in batches of 100  │
   │                                    │                       │          → 1536-dim vectors       │
   │                                    │                       │── INSERT chunks (bulk) ───────────►│
   │                                    │                       │── UPDATE document ────────────────►│
   │                                    │                       │   status="ready"                  │
   │                                    │                       │   chunk_count=N                   │
   │                                    │                       │                    │              │
   │─ (polling GET /documents/ every 5s) ──────────────────────►│                    │              │
   │◄ [{...status:"ready"...}] ─────────────────────────────────│                    │              │
   │  [UI updates badge to green "ready"]                       │                    │              │
```

### Flow 3: Q&A (LangGraph Mode)

```
Browser         nginx      FastAPI /qa/ask          LangGraph Graph              PostgreSQL
   │               │              │                        │                          │
   │─ POST /qa/ask ►│─────────────►│                        │                          │
   │  {question, document_ids}    │                        │                          │
   │  + Bearer token              │                        │                          │
   │                              │─ get_current_user() ───┤                          │
   │                              │─ build_qa_graph() ─────►│                          │
   │                              │─ graph.ainvoke({...}) ──►│                          │
   │                              │                        │                          │
   │                              │              [supervisor_node]                    │
   │                              │              LLM: "retrieval" or "fallback"?      │
   │                              │              → "retrieval"                        │
   │                              │                        │                          │
   │                              │              [query_expansion_node]               │
   │                              │              LLM: generate 3 sub-queries          │
   │                              │              → ["What is X?", "Define X", ...]   │
   │                              │                        │                          │
   │                              │              [retrieval_node]                     │
   │                              │              for each query (4 total):            │
   │                              │                dense: pgvector HNSW search ──────►│
   │                              │                sparse: BM25 over all chunks ──────►│
   │                              │                RRF fusion → deduplicate           │
   │                              │              cross-encoder rerank top 5           │
   │                              │                        │                          │
   │                              │              [synthesis_node]                     │
   │                              │              LLM: answer with citations           │
   │                              │              "...as stated in [Doc: X, Page: 3]"  │
   │                              │                        │                          │
   │                              │              [eval_node]                          │
   │                              │              LLM: rate confidence 0.0–1.0         │
   │                              │              → 0.87                               │
   │                              │                        │                          │
   │◄── 200 {answer, citations, confidence: 0.87, model_used} ─│                     │
   │                              │                        │                          │
   │  [UI renders markdown answer + citation panel + confidence badge]                │
```

### Flow 4: Q&A (MCP Mode)

```
Browser         nginx      FastAPI /qa/ask/mcp       MCPDocumentServer       Anthropic API    PostgreSQL
   │               │              │                        │                       │               │
   │─ POST ask/mcp ►│─────────────►│                        │                       │               │
   │                              │─ MCPDocumentServer(db) ►│                       │               │
   │                              │─ server.answer() ───────►│                       │               │
   │                              │                        │                       │               │
   │                              │               Turn 1:  │                       │               │
   │                              │               messages=[{role:user, q}]        │               │
   │                              │               client.messages.create() ────────►│               │
   │                              │               tools=ALL_MCP_TOOLS              │               │
   │                              │                        │◄── stop_reason:"tool_use"             │
   │                              │                        │    tool: list_documents               │
   │                              │                        │─ _tool_list() ─────────────────────────►│
   │                              │                        │◄─ [{id,name,pages}, ...]              │
   │                              │                        │                       │               │
   │                              │               Turn 2:  │                       │               │
   │                              │               messages += tool_result          │               │
   │                              │               client.messages.create() ────────►│               │
   │                              │                        │◄── stop_reason:"tool_use"             │
   │                              │                        │    tool: search_documents             │
   │                              │                        │─ _tool_search() ───────────────────────►│
   │                              │                        │  hybrid retrieval + rerank            │
   │                              │                        │◄─ {passages:[...]}    │               │
   │                              │                        │                       │               │
   │                              │               Turn 3:  │                       │               │
   │                              │               messages += tool_result          │               │
   │                              │               client.messages.create() ────────►│               │
   │                              │                        │◄── stop_reason:"end_turn"             │
   │                              │                        │    final answer text                  │
   │                              │                        │                       │               │
   │◄── 200 {answer, citations, agent_turns:3, tokens_used} ──│                    │               │
```

### Flow 5: Streaming Answer (SSE)

```
Browser             nginx            FastAPI /qa/ask/stream          RAGPipeline
   │                  │                       │                            │
   │─ POST ask/stream ►│──────────────────────►│                            │
   │                  │                       │─ RAGPipeline(db) ──────────►│
   │                  │                       │─ pipeline.stream() ─────────►│
   │                  │                       │                            │─ retrieve candidates
   │                  │                       │                            │─ rerank
   │◄─ data: {"type":"citation","citations":[...]} ────────────────────────│
   │                  │                       │                            │─ stream LLM tokens
   │◄─ data: {"type":"token","content":"The"} │                            │
   │◄─ data: {"type":"token","content":" answer"} ──────────────────────── │
   │◄─ data: {"type":"token","content":" is..."} ──────────────────────────│
   │◄─ data: {"type":"done","content":""} ─────────────────────────────────│
   │◄─ data: [DONE] ──────────────────────────│                            │
   │                  │                       │                            │
   │ [Frontend reads EventSource, appends tokens to message]               │
```

**SSE headers set by FastAPI**:
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no   ← tells nginx NOT to buffer the stream
```

---

## 16. Where Files Live — Quick Reference

| Task | File(s) |
|------|---------|
| Change LLM model | `backend/app/config.py` → `openai_model` / `anthropic_model` |
| Change embedding dim | `backend/app/config.py` → `embedding_dimension` (+ re-migrate + re-index!) |
| Add API route | `backend/app/api/routes/` + register in `backend/app/main.py` |
| Add DB table | `backend/app/models/` + `make migration msg="..."` + `make migrate` |
| Add Celery task | `backend/app/workers/tasks.py` |
| Add LangGraph node | `backend/app/agents/graph.py` |
| Add MCP tool | `backend/app/mcp/tools.py` + handle in `server.py._execute_tool()` |
| Change chunk size | `backend/app/config.py` → `chunk_size` / `chunk_overlap` |
| Add frontend page | `frontend/src/pages/` + register in `frontend/src/App.tsx` |
| Change API base URL | `frontend/.env` → `VITE_API_URL` |
| Add env variable | `backend/app/config.py` `Settings` class + `.env.example` |
| Run all tests | `make test` → `pytest backend/tests/ -v --cov=app` |
| View task queue | `http://localhost:5555` (Flower) |
| View API docs | `http://localhost/docs` (Swagger UI) |
| View metrics | `http://localhost/metrics` (Prometheus) |

---

## Why `.github/` vs `docs/`

The `.github/` folder is **reserved for GitHub automation only**:
- `.github/workflows/` — CI/CD GitHub Actions
- `.github/ISSUE_TEMPLATE/` — bug/feature issue forms
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist

This document and all project documentation belong in `docs/` — that is the standard location for human-readable reference material. The existing `docs/` folder already contains `API_REFERENCE.md`, `CODING_STANDARDS.md`, and `DEPLOYMENT.md`.