# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        nginx:80                              │
│          /api/*  ──►  backend:8000                          │
│          /*      ──►  frontend:3000                         │
└─────────────────────────────────────────────────────────────┘
         │                          │
┌────────▼────────┐        ┌────────▼────────┐
│  FastAPI        │        │  React SPA      │
│  + LangGraph    │        │  TypeScript     │
│  + RAG Pipeline │        │  TailwindCSS    │
└────────┬────────┘        └─────────────────┘
         │
    ┌────┴─────┐
    │          │
┌───▼───┐  ┌──▼──────┐
│Celery │  │Postgres │  pgvector + pg_trgm
│Worker │  │:5432    │
└───┬───┘  └────┬────┘
    │            │
┌───▼────────────▼───┐
│       Redis:6379    │
│  db0: cache         │
│  db1: Celery broker │
│  db2: Celery results│
└────────────────────┘
```

---

## Backend Modules

### `app/`

```
app/
├── main.py          FastAPI app factory; CORS, Prometheus, router registration, startup
├── config.py        Pydantic-settings: all config from .env, singleton via lru_cache
├── database.py      Async SQLAlchemy engine + session factory + init_db()
│
├── api/routes/
│   ├── auth.py      POST /register, POST /login, GET /me
│   ├── documents.py POST /upload, GET /, DELETE /{id}
│   └── qa.py        POST /ask, POST /ask/mcp, GET /ask/stream
│
├── models/
│   ├── user.py      User (id UUID, email, hashed_password, created_at)
│   └── document.py  Document (id, owner_id→User, filename, status, ...)
│                    Chunk (id, document_id→Document, text, page_number, embedding Vector(1536))
│
├── schemas/         Pydantic v2 request/response schemas (separate from ORM models)
│   ├── user.py
│   ├── document.py
│   └── qa.py
│
├── core/
│   ├── security.py  hash_password, verify_password, create_access_token, decode_access_token
│   └── dependencies.py  get_db(), get_current_user() FastAPI dependencies
│
├── agents/
│   ├── state.py     AgentState, DocumentIngestionState TypedDicts
│   └── graph.py     LangGraph multi-agent graph (5 nodes + ingestion graph)
│
├── rag/
│   ├── embeddings.py   OpenAI / HuggingFace embedder abstraction
│   ├── retriever.py    Hybrid dense (pgvector HNSW) + sparse (BM25) with RRF fusion
│   ├── reranker.py     Cross-encoder reranking (ms-marco-MiniLM-L-12-v2)
│   └── pipeline.py     End-to-end RAG: embed query → retrieve → rerank → return chunks
│
├── processors/
│   ├── pdf_processor.py  Unstructured.io PDF parsing → structured elements
│   └── chunker.py        Semantic chunking with overlap
│
├── workers/
│   ├── celery_app.py   Celery app + Redis broker config
│   └── tasks.py        ingest_document task, cleanup_failed_documents periodic task
│
└── mcp/
    ├── server.py    MCP server definition (for Claude agent tool-use mode)
    └── tools.py     search_documents, list_documents, get_document_metadata tools
```

### Data Flow: PDF Ingestion

```
Client
  POST /api/v1/documents/upload (multipart PDF)
    │
    ▼
FastAPI (documents.py)
  1. Validate MIME type = application/pdf
  2. Validate size ≤ MAX_UPLOAD_SIZE_MB
  3. Save file to /app/uploads/<uuid>.pdf
  4. Create Document record (status=pending)
  5. Enqueue Celery task: ingest_document(document_id)
  6. Return {id, status: "pending"}
    │
    ▼
Celery Worker (tasks.py)
  1. Load PDF from disk
  2. pdf_processor.py → Unstructured → list of Element objects
  3. chunker.py → semantic chunks (size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
  4. embeddings.py → batch embed all chunks (OpenAI or HuggingFace)
  5. Bulk insert Chunk records with embedding vectors into pgvector
  6. Update Document status = "ready" (or "failed" on error)

Client polls GET /api/v1/documents/ every 5 seconds to detect status change
```

### Data Flow: Q&A Query

```
Client
  POST /api/v1/qa/ask {question, document_ids[]}
    │
    ▼
FastAPI (qa.py) → RAGPipeline.run() → LangGraph graph.ainvoke()
    │
    ▼
LangGraph Multi-Agent Graph:

  [supervisor_node]
    Decides: "retrieval" or "fallback"
    ↓ (retrieval)
  [query_expansion_node]
    Generates 3 diverse sub-queries from original question
    ↓
  [retrieval_node]
    For each sub-query:
      1. Embed query (embeddings.py)
      2. pgvector HNSW cosine similarity search (top K)
      3. BM25 sparse retrieval (rank-bm25)
      4. RRF fusion: score = Σ 1/(rank + 60)
    Cross-encoder rerank → top FINAL_TOP_K chunks
    ↓
  [synthesis_node]
    LLM prompt: system(role) + user(question + chunks as context)
    Returns: answer + citations [{chunk_id, page, score}]
    ↓
  [evaluator_node]
    Scores confidence (0-1)
    Detects hallucinations (answer claims not supported by chunks)
    Returns: {answer, citations, confidence, sources}
```

---

## Database Schema

```sql
-- Users
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Documents (one per uploaded PDF)
CREATE TABLE documents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename    TEXT NOT NULL,
  file_path   TEXT NOT NULL,
  status      TEXT NOT NULL,     -- pending | processing | ready | failed
  page_count  INTEGER,
  chunk_count INTEGER,
  created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_status ON documents(status);

-- Chunks (many per document, store embedding vectors)
CREATE TABLE chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  text        TEXT NOT NULL,
  page_number INTEGER,
  embedding   vector(1536)        -- pgvector; MUST match EMBEDDING_DIMENSION
);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_embedding ON chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);  -- HNSW params
```

**pgvector constraints**:
- HNSW index max dimensions: 2000 — use 1536 (OpenAI `text-embedding-3-large`)
- Changing `EMBEDDING_DIMENSION` requires dropping and recreating the index + re-ingesting all documents

---

## Frontend Architecture

```
src/
├── main.tsx          React 18 root, QueryClientProvider, BrowserRouter
├── App.tsx           Routes: /login → LoginPage, / → DashboardPage (PrivateRoute)
├── index.css         Tailwind base + global styles
│
├── api/
│   └── client.ts     Axios instance (base=/api/v1), authApi, docsApi, qaApi
│                     Request interceptor: adds Authorization header from Zustand store
│                     Response interceptor: 401 → clear auth + redirect /login
│
├── store/
│   └── authStore.ts  Zustand store: {token, user} persisted to localStorage
│
├── pages/
│   ├── LoginPage.tsx     Register/Login form; calls authApi; stores JWT in Zustand
│   └── DashboardPage.tsx Main layout: sidebar (doc list + upload) + main (chat)
│
├── components/
│   ├── PDFUpload.tsx     react-dropzone; POST /documents/upload; shows progress
│   ├── DocumentList.tsx  Displays docs with status badges; 5s polling for "processing"
│   ├── ChatInterface.tsx Chat messages + question input; calls qaApi.ask()
│   └── CitationPanel.tsx Renders citations from Q&A response
│
└── hooks/              Custom hooks (empty — extract logic here as components grow)
```

**State management rules**:
- **Zustand** (`authStore`): auth token + user profile — persisted, client-only
- **TanStack Query**: all server data (documents list, Q&A responses) — cached, background-refreshed
- **Local state** (`useState`): ephemeral UI state (input values, modal open/close)

---

## Infrastructure

### Docker Compose Services

| Service | Image | Purpose | Depends On |
|---------|-------|---------|------------|
| `postgres` | pgvector/pgvector:pg16 | Vector DB | — |
| `redis` | redis:7-alpine | Broker + cache | — |
| `backend` | ./backend | FastAPI + RAG | postgres, redis |
| `worker` | ./backend | Celery ingestion worker | postgres, redis |
| `beat` | ./backend | Celery scheduler (cleanup) | redis |
| `flower` | ./backend | Celery monitor UI :5555 | redis |
| `frontend` | ./frontend | React SPA :3000 | — |
| `nginx` | nginx:alpine | Reverse proxy :80 | backend, frontend |

### Nginx Routing

```nginx
/api/*   →  backend:8000   (strip /api prefix? No — FastAPI routes include /api/v1/)
/*       →  frontend:3000
```

### Environment Tiers

| Variable | Development | Production |
|----------|-------------|------------|
| `APP_ENV` | `development` | `production` |
| `SECRET_KEY` | any | cryptographically random 32+ chars |
| `POSTGRES_PASSWORD` | `postgres` | strong password |
| `ALLOWED_ORIGINS` | localhost URLs | actual domain(s) |
| `LANGCHAIN_TRACING_V2` | optional | optional |

---

## Observability

| Signal | Implementation | Endpoint/Access |
|--------|----------------|-----------------|
| Structured logs | `structlog` JSON | Docker logs |
| HTTP metrics | `prometheus-fastapi-instrumentator` | `GET /metrics` |
| LLM traces | LangSmith (optional) | LangSmith dashboard |
| Celery queues | Flower | `http://localhost:5555` |
| Health check | FastAPI | `GET /health` |

---

## Extending the System

### New LLM Provider

1. Add API key to `Settings` in `config.py`
2. Add conditional in `agents/graph.py` where `ChatOpenAI` / `ChatAnthropic` is instantiated
3. Add `primary_llm` literal variant

### New Embedding Provider

1. Add model name to `Settings`
2. Update `rag/embeddings.py::get_embedder()` factory
3. Update `EMBEDDING_DIMENSION` — requires dropping HNSW index and re-ingesting

### New Document Type (e.g., DOCX)

1. Add MIME type check in `api/routes/documents.py`
2. Add parser in `processors/` (similar to `pdf_processor.py`)
3. Route by MIME type in `workers/tasks.py`

### MCP / Agentic Mode

The `/api/v1/qa/ask/mcp` endpoint uses Claude with MCP tool-use instead of the LangGraph graph:
- Tools defined in `mcp/tools.py`: `search_documents`, `list_documents`, `get_document_metadata`
- Claude calls these tools autonomously to build its context before answering
- `mcp/server.py` defines the MCP server for external MCP clients (e.g., Claude Desktop)
