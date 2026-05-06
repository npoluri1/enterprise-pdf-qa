# Coding Standards

## Python (Backend)

### Style Rules

| Rule | Value |
|------|-------|
| Max line length | 100 characters |
| Formatter | ruff format |
| Linter | ruff check |
| Type checker | mypy --strict |
| Python version | 3.11+ |

### Module Structure

Every Python module must start with:
```python
"""One-line module docstring."""
from __future__ import annotations
```

### Type Annotations

All functions require type annotations on every parameter and return value:

```python
# Required
async def embed_text(text: str, model: str = "text-embedding-3-large") -> list[float]:
    ...

# Forbidden
async def embed_text(text, model="text-embedding-3-large"):
    ...
```

Use built-in generic types (`list[str]`, `dict[str, int]`, `tuple[str, ...]`) — not `List`, `Dict`, `Tuple` from `typing`.

Use `X | None` instead of `Optional[X]`.

Use `X | Y` instead of `Union[X, Y]`.

### Async Rules

- All functions that touch the database, filesystem, or network must be `async def`
- Never call `asyncio.run()` from within an async context
- Never use `asyncio.get_event_loop()` — use `asyncio.get_running_loop()` if needed
- Never use `@lru_cache` on async functions or functions that return async clients (Celery task gotcha)

```python
# Correct — Celery tasks
async def _ingest(document_id: uuid.UUID) -> None:
    async with get_db_session() as db:
        ...

@celery_app.task
def ingest_document(document_id: str) -> None:
    asyncio.run(_ingest(uuid.UUID(document_id)))   # OK in sync Celery task entry point
```

### Logging

Use `structlog` — never `print()`, never bare `logging`:

```python
import structlog
log = structlog.get_logger(__name__)

log.info("document.ingested", document_id=str(doc_id), chunk_count=n)
log.warning("retrieval.empty", query=query[:100])
log.error("llm.failed", error=str(e), exc_info=True)
```

Key-value pairs in log calls: use `snake_case` keys, keep values short and serializable.

### Error Handling

- Raise `HTTPException` (not generic `Exception`) from route handlers
- Include meaningful `detail` strings — they reach the client
- Never expose stack traces, internal paths, or DB errors to the client
- Log the full exception server-side before raising a sanitized `HTTPException`

```python
# Correct
try:
    doc = await db.get(Document, doc_id)
except Exception as e:
    log.error("db.get_failed", doc_id=str(doc_id), error=str(e), exc_info=True)
    raise HTTPException(status_code=500, detail="Failed to retrieve document")

if doc is None:
    raise HTTPException(status_code=404, detail="Document not found")

if doc.owner_id != current_user.id:
    raise HTTPException(status_code=403, detail="Access denied")
```

### Database Access

- Always use `AsyncSession` — never the sync `Session`
- Get session via `Depends(get_db)` in route functions
- Use ORM objects for reads; use `bulk_insert_mappings` for large batch inserts
- Commit at the end of a write operation; rollback in `except` blocks

```python
async def create_document(db: AsyncSession, owner_id: uuid.UUID, filename: str) -> Document:
    doc = Document(owner_id=owner_id, filename=filename, status="pending")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc
```

### Pydantic Schemas

- All API request bodies and response models use Pydantic v2 `BaseModel`
- Use `model_validator` and `field_validator` for cross-field validation
- Response schemas must exclude sensitive fields (passwords, internal paths)
- Schema files live in `app/schemas/`, separate from ORM models in `app/models/`

### Configuration

- All config via `app.config.settings` (singleton from `get_settings()`)
- Never `os.environ.get()` directly in app code — only in `config.py`
- Secrets must have no default value (or raise `ValueError` if empty in production)
- New config: add to `Settings` class + document in `.env.example`

---

## TypeScript (Frontend)

### Style Rules

| Rule | Value |
|------|-------|
| TypeScript | Strict mode (`"strict": true`) |
| Linter | ESLint + @typescript-eslint |
| Target | ES2020 |
| Module | ESNext |

### Type Safety

- Never use `any` — use `unknown` and narrow, or define proper types
- No non-null assertions (`!`) without a comment explaining why it can't be null
- No `// @ts-ignore` or `// @ts-expect-error` in production code
- Prefer `interface` for object shapes that may be extended, `type` for unions/aliases

```typescript
// Correct
interface Document {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
}

// Forbidden
const handleResponse = (data: any) => { ... }
```

### Component Rules

- Functional components only — no class components
- Explicit prop types — never rely on inference for component props
- Extract complex logic into custom hooks in `src/hooks/`
- Keep components focused — if a component exceeds ~150 lines, consider splitting

```typescript
// Correct — explicit props interface
interface ChatInterfaceProps {
  selectedDocIds: string[]
  onNewMessage: (message: Message) => void
}

export function ChatInterface({ selectedDocIds, onNewMessage }: ChatInterfaceProps) { ... }
```

### Data Fetching

- Use TanStack Query (`useQuery`, `useMutation`) for all server state
- No `useEffect` for data fetching — that belongs in query hooks
- Set appropriate `staleTime` and `gcTime` for each query based on data freshness needs
- Handle loading, error, and empty states explicitly in components

```typescript
// Correct
const { data: documents, isLoading, error } = useQuery({
  queryKey: ['documents'],
  queryFn: () => docsApi.list(),
  staleTime: 5_000,
})

// Forbidden
useEffect(() => {
  fetch('/api/v1/documents/').then(r => r.json()).then(setDocuments)
}, [])
```

### API Client

- All API calls go through `src/api/client.ts` — never raw `fetch()` in components
- Axios interceptors handle auth headers and 401 redirects centrally
- Type all API response shapes with TypeScript interfaces

### State Management

- Zustand only for truly global, client-side state (auth)
- Component state (`useState`) for UI-only ephemeral state
- TanStack Query for server-mirrored state
- Do not put server data into Zustand — that duplicates TanStack Query's cache

### CSS

- TailwindCSS utility classes only — no `style={{}}` props
- No custom CSS in component files — add to `index.css` if truly needed
- Use Tailwind `@apply` sparingly and only in `index.css`

---

## Git Standards

### Commits

Follow Conventional Commits: `type(scope): summary`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

Summary: imperative mood, max 72 chars, no period at end.

### Files to Never Commit

- `.env` (gitignored)
- `backend/uploads/` (gitignored)
- `__pycache__/`, `*.pyc` (gitignored)
- `node_modules/` (gitignored)
- `backend/.venv/` (gitignored)
- Any file containing an API key, password, or secret

### Code Review Standards

Reviewer expectations:
- Check for security issues (see SECURITY.md checklist)
- Verify type annotations are complete
- Confirm tests cover the new/changed behavior
- Ensure no debug code (`print`, `console.log`) left in
- Validate migration is included for model changes
- Check `.env.example` updated for new env vars

Author expectations:
- Self-review the diff before requesting review
- Respond to all review comments before merging
- Keep PR size manageable (< 400 lines changed ideally)
