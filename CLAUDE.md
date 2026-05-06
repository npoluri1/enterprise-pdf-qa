# CLAUDE.md — Enterprise PDF Q&A

## Project Overview

Enterprise PDF Q&A platform: upload PDFs, ask questions, get AI-generated answers with source citations.
Stack: FastAPI + LangGraph + pgvector (backend), React 18 + TypeScript + TailwindCSS (frontend), Docker Compose (8 containers).

---

## Quick Commands

```bash
# Start all services
make up                     # docker compose up -d --build

# Development (hot-reload)
make dev                    # backend + frontend with volume mounts

# Stop services
make down

# Logs
make logs                   # all containers
docker compose logs -f backend

# Database migrations
make migrate                # alembic upgrade head
make migration msg="desc"   # alembic revision --autogenerate

# Tests
make test                   # pytest backend/tests/
make lint                   # ruff + mypy (backend), eslint (frontend)

# Access UIs
# API docs:    http://localhost/docs
# Flower:      http://localhost:5555
# Prometheus:  http://localhost/metrics
```

---

## Architecture

```
nginx:80
  ├── /api/*  → backend:8000  (FastAPI)
  └── /*      → frontend:3000 (React SPA)

backend:8000
  ├── POST /api/v1/auth/register|login
  ├── POST /api/v1/documents/upload  → Celery task → worker
  ├── GET  /api/v1/documents/
  └── POST /api/v1/qa/ask|ask/mcp|ask/stream

worker (Celery)
  └── ingest_document task:
        PDF → Unstructured → chunks → embeddings → pgvector

postgres:5432  (pgvector + pg_trgm + uuid-ossp)
redis:6379     (Celery broker db1, result db2, app cache db0)
flower:5555    (Celery queue monitor)
```

### Multi-Agent Q&A Flow (LangGraph)

```
User Question
  → Supervisor        (route: retrieval | fallback)
  → Query Expansion   (3 diverse sub-queries)
  → Retrieval         (pgvector HNSW + BM25 → RRF fusion → cross-encoder rerank)
  → Synthesis         (LLM answer + citations)
  → Evaluator         (confidence score + hallucination check)
```

Key files:
- `backend/app/agents/graph.py` — LangGraph multi-agent orchestration
- `backend/app/rag/pipeline.py` — RAG pipeline
- `backend/app/rag/retriever.py` — hybrid dense+sparse retrieval
- `backend/app/config.py` — all settings via pydantic-settings
- `frontend/src/api/client.ts` — Axios API client
- `frontend/src/store/authStore.ts` — Zustand auth state

---

## Environment Setup

Copy `.env.example` to `.env` and set:

```bash
SECRET_KEY=<32+ char random string>       # REQUIRED — change before any deploy
OPENAI_API_KEY=sk-...                      # Required if PRIMARY_LLM=openai
ANTHROPIC_API_KEY=sk-ant-...               # Required if PRIMARY_LLM=anthropic
POSTGRES_PASSWORD=<strong password>        # Change from default "postgres"

# Embedding dimension MUST match pgvector HNSW index (max 2000 for pgvector)
EMBEDDING_DIMENSION=1536                   # Use 1536, NOT 3072 (exceeds pgvector limit)
```

**Never commit `.env`** — it is gitignored. Use `.env.example` for templates.

---

## Coding Standards

### Python (Backend)

- **Python 3.11+**; use `from __future__ import annotations` at module top
- **Type hints everywhere** — all function signatures, return types, class fields
- **Async by default** — all DB calls, HTTP calls, file I/O use `async`/`await`
- **Pydantic v2** for all request/response schemas; never raw dicts at API boundary
- **SQLAlchemy 2.0 async** ORM; never use sync session in async context
- **Settings from `app.config.settings`** — never `os.environ.get()` directly in app code
- **Structured logging** via `structlog` — `log = structlog.get_logger(__name__)`; no bare `print()`
- **Error handling**: raise `HTTPException` with specific status codes; never expose stack traces to clients
- **Dependency injection** via FastAPI `Depends()` for DB sessions, current user, settings

```python
# Good
from __future__ import annotations
import structlog
from app.config import settings

log = structlog.get_logger(__name__)

async def get_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Document:
    ...

# Bad
import os
print("debug")
def get_document(doc_id, db):  # missing types
    ...
```

- **File naming**: `snake_case.py`
- **Class naming**: `PascalCase`
- **Constant naming**: `UPPER_SNAKE_CASE`
- **Max line length**: 100 characters
- **Linter**: `ruff` (configured in `pyproject.toml` or `ruff.toml`)
- **Type checker**: `mypy --strict` on `backend/app/`

### TypeScript (Frontend)

- **TypeScript strict mode** (`"strict": true` in `tsconfig.json`) — no `any`, no `// @ts-ignore`
- **React 18 functional components** only — no class components
- **Custom hooks** in `src/hooks/` for stateful logic extracted from components
- **TanStack Query** for all server state — no manual `useEffect` for data fetching
- **Zustand** for client-only global state (auth token, user profile)
- **No inline styles** — use TailwindCSS utility classes only
- **Named exports** for components; default export only for page-level components

```typescript
// Good
export function DocumentCard({ doc }: { doc: Document }) { ... }

// Bad
export default function(props: any) { ... }
```

- **File naming**: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks
- **Linter**: ESLint with `@typescript-eslint` plugin
- **Formatter**: Prettier (if configured)

### Both

- **No TODO comments** left in merged code — open a ticket instead
- **No commented-out code** — use git history
- **No hardcoded secrets, URLs, or credentials** in source files
- **Comments only for non-obvious WHY** — not what the code does

---

## Security Requirements

See [SECURITY.md](SECURITY.md) for full policy.

**Non-negotiable rules:**

1. **SECRET_KEY** must be cryptographically random, 32+ chars; never the default value in production
2. **All API endpoints** (except `/health`, `/api/v1/auth/*`) require `Authorization: Bearer <token>`
3. **File uploads**: validate MIME type (`application/pdf` only), enforce `MAX_UPLOAD_SIZE_MB`, store outside web root (`/app/uploads/`)
4. **SQL**: use SQLAlchemy ORM or parameterized queries only — never string-format SQL
5. **Passwords**: bcrypt with default cost factor (12+); never store plaintext or MD5/SHA1
6. **CORS**: `allowed_origins` must be explicit list; never `["*"]` in production
7. **JWT**: HS256 with `SECRET_KEY`; always validate `exp` claim; never accept tokens without `sub`
8. **Dependencies**: pin all versions in `requirements.txt`; audit with `pip-audit` before release
9. **Secrets in `.env`**: never `os.environ["KEY"]` fallback to empty string for secrets — fail fast
10. **LLM prompt injection**: sanitize user-supplied text before including in system prompts

---

## Testing Standards

See [TESTING.md](TESTING.md) for full guide.

```bash
# Run all backend tests
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py -v

# Frontend tests
cd frontend && npm test
```

**Requirements:**
- All new API endpoints need at least one integration test
- Business logic (RAG pipeline, agent graph, chunker) needs unit tests
- Use `pytest-asyncio` for async tests; never `asyncio.run()` in test bodies
- Mock external API calls (OpenAI, Anthropic, Unstructured) in tests — never hit live APIs in CI
- Minimum 70% coverage on `backend/app/`; coverage reports generated in CI

---

## Known Constraints & Gotchas

| Issue | Rule |
|-------|------|
| pgvector HNSW index max dims = 2000 | Use `EMBEDDING_DIMENSION=1536`, never 3072 |
| Celery workers + asyncio | Workers use `asyncio.run()`, never `@lru_cache` on async clients |
| Login endpoint | Must use `application/x-www-form-urlencoded`, not JSON |
| File upload | Never set explicit `Content-Type: multipart/form-data` — let Axios set boundary |
| Pydantic v2 list fields from env | Must be JSON array in `.env`: `ALLOWED_ORIGINS=["http://..."]` |
| LangGraph TypedDict imports | Import at module level, not inside function bodies |
| bcrypt compatibility | Use `bcrypt` directly (4.2.1+), not `passlib.handlers.bcrypt` |
| Docker internal hostnames | DB host = `postgres`, Redis host = `redis` (not `localhost`) |

---

## Adding New Features

1. **New API route**: add router in `backend/app/api/routes/`, include in `main.py` under `/api/v1`
2. **New DB model**: add SQLAlchemy model in `backend/app/models/`, create Alembic migration (`make migration`)
3. **New Celery task**: add in `backend/app/workers/tasks.py`, import celery app from `celery_app.py`
4. **New agent node**: add function to `backend/app/agents/graph.py`, register in graph builder
5. **New frontend page**: add component in `frontend/src/pages/`, register route in `App.tsx`
6. **New env var**: add to `Settings` class in `config.py`, document in `.env.example`

---

## LLM Usage in This Codebase

- **Primary LLM**: controlled by `PRIMARY_LLM` env var (`openai` | `anthropic`)
- **Default OpenAI model**: `gpt-4o`
- **Default Anthropic model**: `claude-sonnet-4-6`
- **LangChain wrappers**: use `ChatOpenAI` / `ChatAnthropic` from langchain-openai / langchain-anthropic
- **Prompt templates**: defined inline in agent nodes in `graph.py`; keep system prompts in module-level constants
- **Streaming**: use `astream_events()` on the LangGraph graph; SSE via FastAPI `StreamingResponse`
- **Tracing**: set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` for LangSmith traces

---

## Pull Request Checklist

Before opening a PR:
- [ ] `make lint` passes with zero warnings
- [ ] `make test` passes (no regressions)
- [ ] New env vars added to `.env.example`
- [ ] New DB models have an Alembic migration
- [ ] No secrets or `.env` values committed
- [ ] SECURITY.md consulted for any auth / file-handling / LLM changes
- [ ] `EMBEDDING_DIMENSION` not changed without re-running migrations + re-indexing
