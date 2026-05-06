# Contributing Guide

## Development Setup

### Prerequisites

- Docker Desktop 4.x + Docker Compose v2
- Python 3.11+ (for local backend dev without Docker)
- Node.js 20+ (for local frontend dev without Docker)
- `make` (comes with Git for Windows; or use WSL)

### First-Time Setup

```bash
# 1. Clone repo
git clone <repo-url>
cd enterprise-pdf-qa

# 2. Copy and configure environment
cp .env.example .env
# Edit .env: set SECRET_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY, etc.

# 3. Start all services
make up

# 4. Verify
curl http://localhost/health   # → {"status":"ok"}
```

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev                    # Vite dev server on :5173
```

---

## Branching Strategy

```
main          ← production-ready, protected
  └── develop ← integration branch
        └── feature/<ticket>-short-desc
        └── fix/<ticket>-short-desc
        └── chore/<what>
```

- **Branch from** `develop`
- **PR target**: `develop` (not `main`)
- **Main** is updated only via release PRs from `develop`
- One feature per branch — keep PRs small and focused

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short imperative summary>

[optional body — WHY, not WHAT]

[optional footer: Breaking changes, closes #issue]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

**Scope** (optional): `auth`, `rag`, `agents`, `workers`, `frontend`, `docker`, `deps`

**Examples**:
```
feat(rag): add BM25 sparse retrieval to hybrid pipeline
fix(auth): reject tokens missing exp claim
chore(deps): bump anthropic to 0.40.0
docs: add TESTING.md with pytest guide
```

- Summary line max 72 characters
- Use imperative mood: "add", "fix", "remove" — not "added", "fixes", "removed"
- Reference issues: `Closes #42`

---

## Pull Request Process

1. **Run checks locally** before pushing:
   ```bash
   make lint    # must pass with zero errors
   make test    # must pass with no regressions
   ```

2. **Fill out the PR template** — title, summary, test plan, checklist

3. **Keep PRs focused** — one logical change per PR; split unrelated fixes

4. **Review turnaround**: expect review within 2 business days

5. **Merge strategy**: squash-merge into `develop`; rebase-merge for release PRs into `main`

### PR Title Format

Same as commit messages: `feat(scope): summary`

---

## Code Style

### Python

| Rule | Tool | Config |
|------|------|--------|
| Linting + formatting | `ruff` | `ruff.toml` |
| Type checking | `mypy --strict` | `mypy.ini` |
| Import sorting | `ruff` (isort rules) | — |

```bash
cd backend
ruff check app/          # lint
ruff format app/         # format
mypy app/                # type check
```

**Key rules**:
- `from __future__ import annotations` at top of every module
- All function parameters and return values must have type annotations
- No `Any` unless absolutely unavoidable (document why with a comment)
- `async def` for all functions that touch DB, filesystem, or network
- `structlog` for logging — no `print()`, no bare `logging.getLogger()`

### TypeScript / React

| Rule | Tool | Config |
|------|------|--------|
| Linting | ESLint | `.eslintrc` |
| Type checking | `tsc --noEmit` | `tsconfig.json` |

```bash
cd frontend
npm run lint       # ESLint
npm run type-check # tsc --noEmit
npm run build      # full production build (catches TS errors)
```

**Key rules**:
- Strict TypeScript (`"strict": true`) — no `any`, no non-null assertions without justification
- React 18 functional components only
- TanStack Query for all server state — no `useEffect` for data fetching
- TailwindCSS utility classes only — no inline `style={{}}` props
- Named exports for all components except page-level defaults

---

## Database Migrations

```bash
# After changing a SQLAlchemy model:
make migration msg="add_index_on_chunks_document_id"

# Apply migrations
make migrate

# Check current revision
docker compose exec backend alembic current

# Downgrade one step
docker compose exec backend alembic downgrade -1
```

**Rules**:
- Every PR that changes a model must include the Alembic migration
- Never edit an already-applied migration — create a new one
- Migration filenames: `NNN_snake_case_description.py`
- Test migrations both up and down before submitting PR

---

## Adding Dependencies

### Python

```bash
# Add to requirements.txt with pinned version
echo "new-package==1.2.3" >> backend/requirements.txt

# Verify no conflicts
pip install -r backend/requirements.txt

# Audit for CVEs
pip-audit -r backend/requirements.txt
```

### Node

```bash
cd frontend
npm install <package>@<version>   # --save-dev for dev-only

# Audit
npm audit
```

**Rules**:
- Always pin exact versions in `requirements.txt`
- Run `pip-audit` / `npm audit` and resolve critical/high CVEs before merging
- Justify new dependencies in the PR description — avoid adding deps for trivial tasks

---

## Testing

See [TESTING.md](TESTING.md) for full guide.

```bash
make test                                         # all backend tests
cd backend && pytest tests/test_auth.py -v        # one file
cd backend && pytest -k "test_upload" -v          # by name pattern
```

**Before submitting a PR**:
- New API endpoint → add integration test
- New business logic → add unit test
- Bug fix → add regression test that would have caught the bug

---

## Docker Workflow

```bash
make up           # start all 8 containers
make down         # stop and remove containers (keeps volumes)
make down-v       # stop and remove containers + volumes (fresh DB)
make logs         # tail all logs
make shell        # bash into backend container

# Rebuild a single service after Dockerfile change
docker compose up -d --build backend
```

---

## Troubleshooting Common Issues

| Symptom | Fix |
|---------|-----|
| `HNSW index creation failed` | Set `EMBEDDING_DIMENSION=1536` in `.env` |
| `ValueError: bcrypt` | Ensure `bcrypt==4.2.1` — remove `passlib` if present |
| Login returns 422 | Frontend must send `application/x-www-form-urlencoded` |
| Upload fails with boundary error | Remove explicit `Content-Type` header in Axios upload call |
| Worker crashes on event loop | Use `asyncio.run()`, not `@lru_cache` on async clients in tasks |
| `ALLOWED_ORIGINS` error | Set as JSON: `ALLOWED_ORIGINS=["http://localhost:3000"]` |
| Docker DB connection refused | Use host=`postgres`, not `localhost` inside containers |
