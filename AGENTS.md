# AGENTS.md — Enterprise PDF Q&A

## Quick Commands

```bash
# Start everything (first time + after code changes)
make dev              # builds images, runs migrations, prints URLs
make up-build         # just build + start
make down             # stop
make down-v           # stop + delete volumes (full reset)

# Local development (inside containers)
make shell            # bash in backend container
make psql             # psql shell
make redis-cli        # redis-cli shell

# Tests
cd backend && pytest tests/ -m "not integration" -v   # unit tests only
cd backend && pytest tests/ -m "integration" -v       # needs postgres + redis
make test-frontend    # frontend vitest
make coverage         # backend coverage → backend/htmlcov/index.html

# Lint / type-check (run in this order)
cd backend && ruff check app/ && ruff format --check app/   # ruff lint + format
cd backend && mypy app/ --ignore-missing-imports             # type check
cd frontend && npm run lint                                   # eslint (0 warnings allowed)
cd frontend && npm run type-check                             # tsc --noEmit
cd frontend && npm run build                                  # vite build
```

## Architecture

8 Docker containers: postgres (pgvector), redis, backend (FastAPI), worker (Celery), beat, flower, frontend (React/Vite), nginx. Nginx proxies `/api/*` → backend:8000, `/*` → frontend:3000.

Backend entrypoint: `backend/app/main.py`. Frontend entrypoint: `frontend/src/main.tsx`.

Key paths:
- `backend/app/agents/graph.py` — LangGraph multi-agent orchestration
- `backend/app/rag/pipeline.py` — RAG pipeline (query expansion → retrieval → rerank → answer)
- `backend/app/rag/retriever.py` — hybrid pgvector HNSW + BM25 + RRF fusion
- `backend/app/api/routes/` — FastAPI route handlers
- `backend/app/workers/tasks.py` — Celery tasks (PDF ingestion)
- `frontend/src/components/` — React components
- `frontend/src/hooks/` — Custom hooks + Zustand store

## Multi-Tenant (Multi-Company)

Every user belongs to at least one **Organization** (company). On registration, a personal org is auto-created.

| Model | Table | Purpose |
|-------|-------|---------|
| `Organization` | `organizations` | Company/tenant with unique slug |
| `OrganizationMembership` | `organization_memberships` | User–Org join with role (admin/member) |
| `Document.organization_id` | `documents` | FK → organizations; drives RAG isolation |

**Tenant isolation** is baked into:
- **Document CRUD**: scoped to user's org via `organization_id` filter
- **RAG retrieval**: `HybridRetriever.retrieve()` accepts `organization_id` to filter both dense (pgvector SQL) and sparse (BM25) searches
- **MCP server**: all tool calls scoped by `organization_id`
- **LangGraph agent**: `AgentState.organization_id` passed through graph, consumed by `retrieval_node`
- **QA endpoints**: `_resolve_org()` finds the org from request or falls back to default membership

**API conventions**:
- `POST /organizations/` — create org (creator becomes admin)
- `GET /organizations/` — list user's orgs
- `POST /organizations/{id}/members` — invite member by email
- All document endpoints accept optional `org_id` query param
- All QA endpoints accept optional `organization_id` in request body

## Critical Gotchas

| Rule | Why |
|------|-----|
| `EMBEDDING_DIMENSION=1536` — never 3072 | pgvector HNSW index max is 2000 dimensions |
| Login endpoint uses `application/x-www-form-urlencoded`, not JSON | FastAPI OAuth2PasswordBearer requirement |
| File upload: never set `Content-Type: multipart/form-data` explicitly | Axios must auto-set with boundary |
| DB hostname = `postgres`, Redis = `redis` | Docker internal hostnames, not `localhost` |
| Login uses form data: `username` = email, `password` = password | OAuth2PasswordRequestForm field names |
| LangGraph TypedDict imports at module level, not inside functions | Runtime state resolution requires it |
| Workers use `asyncio.run()`, never `@lru_cache` on async clients | Breaks across worker process boundaries |
| No `os.environ.get()` for settings | All config from `app.config.settings` (pydantic-settings) |
| No bare `print()` or `logging` | Use `structlog.get_logger(__name__)` |

## Coding Conventions

**Python**: Python 3.11+, `from __future__ import annotations` at top, async by default, Pydantic v2 schemas, SQLAlchemy 2.0 async ORM, type hints on all signatures, 100-char line limit.

**TypeScript**: strict mode (no `any`), React 18 functional components, TanStack Query for server state, Zustand for client state, TailwindCSS only (no inline styles), named exports for components.

**Naming**: Python files `snake_case.py`, TS components `PascalCase.tsx`, TS utilities `camelCase.ts`, constants `UPPER_SNAKE_CASE`.

## CI Workflow

`.github/workflows/ci.yml` runs on push/PR to `main`/`develop`:
1. `backend-lint`: ruff check + format + mypy
2. `backend-test`: unit tests, then integration tests (postgres + redis services)
3. `frontend-lint`: npm type-check + eslint + build
4. `frontend-test`: vitest with coverage
5. `security-audit`: pip-audit + npm audit (continue-on-error)
6. `docker-build`: build both images (PR only)

All lint and test jobs must pass. Ruff format is checked, not auto-fixed in CI.

## Adding Features

- **New API route**: add router in `backend/app/api/routes/`, import in `backend/app/main.py`
- **New DB model**: add in `backend/app/models/`, run `make migration msg="desc"`
- **New Celery task**: add function in `backend/app/workers/tasks.py`, import celery app from `celery_app.py`
- **New agent node**: add function in `backend/app/agents/graph.py`, register in `StateGraph`
- **New frontend page**: add component in `frontend/src/pages/`, add route in `App.tsx`
- **New env var**: add to `Settings` class in `backend/app/config.py`, document in `.env.example`
