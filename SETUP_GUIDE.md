# Complete Setup & Operations Guide

This guide covers every operational detail: first-time setup, starting and stopping services, testing all features via API and UI, reading logs for every container, and database access.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [First-Time Build & Start](#first-time-build--start)
4. [Daily Start / Stop Commands](#daily-start--stop-commands)
5. [Verifying All Services](#verifying-all-services)
6. [Step-by-Step Feature Testing](#step-by-step-feature-testing)
7. [Log Reference — Every Container](#log-reference--every-container)
8. [Database Access & Queries](#database-access--queries)
9. [Redis Inspection](#redis-inspection)
10. [Flower Task Monitor](#flower-task-monitor)
11. [Swagger UI Testing](#swagger-ui-testing)
12. [Applying Code Changes](#applying-code-changes)
13. [Common Operations](#common-operations)
14. [All Known Issues & Fixes](#all-known-issues--fixes)

---

## Prerequisites

```bash
# Verify Docker is installed and running
docker --version
# Expected: Docker version 24.x.x or higher

docker compose version
# Expected: Docker Compose version v2.x.x

# Verify Docker Desktop Linux engine is active
docker ps
# Expected: empty table (no error)
```

If `docker ps` returns an error about the pipe not found, start Docker Desktop from the Windows Start menu and wait ~30 seconds.

---

## Environment Configuration

The `.env` file controls every runtime setting. It is already present in the project root.

### Opening the file

```
enterprise-pdf-qa/.env
```

### Required settings

```env
# ── LLM (at least one required) ──────────────────────────────
OPENAI_API_KEY=sk-proj-...       # From https://platform.openai.com/api-keys
                                  # Must have billing credits

ANTHROPIC_API_KEY=sk-ant-...     # From https://console.anthropic.com
                                  # Only needed if PRIMARY_LLM=anthropic

# ── Which LLM to use ─────────────────────────────────────────
PRIMARY_LLM=openai               # openai | anthropic

# ── Security ─────────────────────────────────────────────────
SECRET_KEY=change-me-super-secret-key-at-least-32-chars
# Generate a strong key: openssl rand -hex 32

# ── Embeddings (DO NOT CHANGE DIMENSION) ─────────────────────
EMBEDDING_DIMENSION=1536         # MUST be 1536 — pgvector HNSW limit is 2000 dims
                                  # Changing this requires a full data reset

# ── CORS (browsers allowed to call the API) ──────────────────
ALLOWED_ORIGINS=["http://localhost","http://localhost:80","http://localhost:3000","http://localhost:5173","http://127.0.0.1"]
```

### After changing `.env`

```bash
# Must do a full restart — restart alone does NOT reload env vars
docker compose down
docker compose up -d
```

---

## First-Time Build & Start

### Step 1 — Build all images

```bash
cd enterprise-pdf-qa
docker compose build --no-cache
```

This pulls base images and installs all Python + Node dependencies.
**Duration: 5–10 minutes** on first run.

Watch progress:
```bash
# The build runs in Docker's buildkit — watch output scroll by
# Look for these markers:
#   "Successfully installed ..." → Python packages done
#   "npm ci" → Node packages done
#   "exporting to image" → image being finalized
```

### Step 2 — Start all containers

```bash
docker compose up -d
```

Expected output:
```
Container pdf_qa_postgres  Started
Container pdf_qa_redis     Started
Container pdf_qa_backend   Started
Container pdf_qa_worker    Started
Container pdf_qa_beat      Started
Container pdf_qa_flower    Started
Container pdf_qa_frontend  Started
Container pdf_qa_nginx     Started
```

### Step 3 — Wait for healthy state

```bash
docker compose ps
```

Wait until `pdf_qa_postgres` and `pdf_qa_redis` both show `(healthy)`:
```
pdf_qa_postgres   Up X seconds (healthy)
pdf_qa_redis      Up X seconds (healthy)
```

This usually takes 10–20 seconds.

### Step 4 — Confirm backend started

```bash
docker compose logs backend --tail=5
```

Must contain:
```
INFO:     Application startup complete.
```

### Step 5 — Run a health check

```bash
curl http://localhost/health
```

Expected: `{"status":"ok","env":"development"}`

If you get a connection error, wait 10 more seconds and try again — nginx may still be connecting to the backend.

---

## Daily Start / Stop Commands

### Start everything

```bash
docker compose up -d
```

### Stop everything (keeps all data)

```bash
docker compose down
```

### Restart all services

```bash
docker compose restart
```

### Restart one service

```bash
docker compose restart backend
docker compose restart worker
docker compose restart frontend
docker compose restart nginx
```

### Stop one service

```bash
docker compose stop worker
```

### Start one stopped service

```bash
docker compose start worker
```

---

## Verifying All Services

### Full status check

```bash
docker compose ps
```

All 8 containers should be `Up`. postgres and redis should be `(healthy)`.

### Health check endpoints

```bash
# Application health (via nginx)
curl http://localhost/health

# Backend direct health (bypassing nginx)
curl http://localhost:8000/health

# Frontend serving check
curl -I http://localhost
# Expected: HTTP/1.1 200 OK

# Flower running
curl -I http://localhost:5555
# Expected: HTTP/1.1 200 OK
```

### Database connectivity

```bash
docker compose exec postgres pg_isready -U postgres
# Expected: /var/run/postgresql:5432 - accepting connections
```

### Redis connectivity

```bash
docker compose exec redis redis-cli ping
# Expected: PONG
```

### Worker is connected

```bash
docker compose logs worker --tail=5 | grep "ready\|celery@"
# Expected: celery@<container-id> ready.
```

---

## Step-by-Step Feature Testing

All examples use `curl` from a terminal. Replace `$TOKEN` with a real token from the login step.

### Get a token first

```bash
# Register (first time only)
curl -X POST http://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}'

# Login — save the token
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@example.com&password=Demo1234!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token acquired: ${TOKEN:0:30}..."
```

### Test: Auth endpoints

```bash
# 1. Register new user
curl -X POST http://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@test.com","password":"Pass1234!","full_name":"New User"}'
# Expected 201: {"id":"...","email":"newuser@test.com",...}

# 2. Login
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=newuser@test.com&password=Pass1234!"
# Expected 200: {"access_token":"eyJ...","token_type":"bearer"}

# 3. Get current user
curl http://localhost/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
# Expected 200: {"id":"...","email":"...","is_active":true,...}

# 4. Unauthenticated request (must fail)
curl http://localhost/api/v1/auth/me
# Expected 401: {"detail":"Not authenticated"}

# 5. Wrong password (must fail)
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@example.com&password=WrongPass"
# Expected 401: {"detail":"Invalid credentials"}
```

### Test: Document endpoints

```bash
# 6. Upload a PDF
curl -X POST http://localhost/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/document.pdf"
# Expected 201: {"id":"...","status":"pending","original_name":"document.pdf",...}

# Save the document ID
DOC_ID="<paste-id-from-above>"

# 7. List all documents
curl http://localhost/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN"
# Expected 200: {"items":[{"id":"...","status":"pending"|"processing"|"ready",...}],"total":1}

# 8. Poll status until "ready" (run this multiple times)
curl "http://localhost/api/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
# Keep running until status == "ready"

# 9. Upload non-PDF (must fail)
echo "not a pdf" > /tmp/test.txt
curl -X POST http://localhost/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.txt"
# Expected 400: {"detail":"Only PDF files are accepted"}

# 10. Upload oversized file (must fail — requires a >50MB file)
# Expected 413: {"detail":"File exceeds 50 MB limit"}

# 11. Delete a document
curl -X DELETE "http://localhost/api/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
# Expected 204: (no body)
```

### Test: Q&A endpoints

```bash
# 12. Ask a question (LangGraph multi-agent)
curl -X POST http://localhost/api/v1/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"question\": \"What are the main topics in this document?\",
    \"document_ids\": [\"$DOC_ID\"],
    \"top_k\": 5,
    \"use_reranker\": true
  }"
# Expected 200: {"answer":"...","citations":[...],"confidence":0.85,...}

# 13. Ask without specifying documents (searches all)
curl -X POST http://localhost/api/v1/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the key points"}'
# Expected 200: answer from all available docs

# 14. Ask via Claude + MCP (requires ANTHROPIC_API_KEY)
curl -X POST http://localhost/api/v1/qa/ask/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What are the conclusions?\", \"document_ids\": [\"$DOC_ID\"]}"
# Expected 200: {"answer":"...","agent_turns":2,...}

# 15. Question too short (must fail)
curl -X POST http://localhost/api/v1/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hi"}'
# Expected 422: {"detail":[{"msg":"String should have at least 3 characters",...}]}
```

### Test: UI walkthrough checklist

Open http://localhost and verify each step:

```
[ ] 1.  Login page loads at http://localhost
[ ] 2.  Register a new account — success toast appears
[ ] 3.  Log in — redirected to /dashboard
[ ] 4.  Dashboard shows: upload zone, empty document list, empty chat
[ ] 5.  Drag a PDF onto the upload zone — toast shows "uploaded — processing…"
[ ] 6.  Document appears in list with "pending" then "processing" badge (auto-updates)
[ ] 7.  Document changes to "ready" badge (auto-updates, no page refresh needed)
[ ] 8.  Click the document card — it highlights blue (selected)
[ ] 9.  Type a question in the chat input and press Enter
[ ] 10. Spinner appears while processing
[ ] 11. Answer appears with model name and confidence score
[ ] 12. "Sources (N)" panel appears below the answer
[ ] 13. Click a source row — excerpt text expands
[ ] 14. Switch to "Claude + MCP" mode (purple button) and ask again
[ ] 15. Logout button (top right) — logs out and returns to /login
```

---

## Log Reference — Every Container

### How to read logs

```bash
# Follow a service live (Ctrl+C to stop)
docker compose logs -f <service>

# Show last N lines
docker compose logs <service> --tail=<N>

# Show logs since a time
docker compose logs <service> --since=10m
docker compose logs <service> --since=2024-01-15T10:00:00

# Filter by keyword (Linux/Mac)
docker compose logs <service> | grep "ERROR"

# Filter by keyword (PowerShell/Windows)
docker compose logs <service> | Select-String "ERROR"
```

---

### `backend` — FastAPI application

```bash
docker compose logs -f backend
docker compose logs backend --tail=100
```

**Startup sequence to verify:**
```
startup env=development                      ← App config loaded
CREATE EXTENSION IF NOT EXISTS vector        ← pgvector extension ensured
Application startup complete.                ← FastAPI ready
```

**Normal request traffic:**
```
POST /api/v1/auth/login 200                  ← Login OK
GET  /api/v1/documents/ 200                  ← Document list OK
POST /api/v1/documents/upload 201            ← Upload accepted
POST /api/v1/qa/ask 200                      ← Q&A answered
GET  /health 200                             ← Health check (frequent, normal)
GET  /metrics 200                            ← Prometheus scrape (normal)
```

**Q&A pipeline trace:**
```
supervisor_routed route=retrieval            ← Supervisor sent to RAG
supervisor_routed route=fallback             ← Supervisor sent to fallback (no relevant docs)
Retrieved 5 chunks after reranking.          ← Retrieval succeeded
```

**Error patterns:**
```
POST /api/v1/documents/upload 422            ← Validation failed (wrong type/size)
POST /api/v1/auth/login 401                  ← Wrong credentials
AuthenticationError                          ← Invalid API key → fix OPENAI_API_KEY
insufficient_quota                           ← No OpenAI credits → add billing
RateLimitError                               ← Too many requests → wait and retry
```

---

### `worker` — Celery ingestion worker

```bash
docker compose logs -f worker
docker compose logs worker --tail=100
```

**Startup sequence to verify:**
```
celery@<container> ready.                    ← Worker connected to Redis
Events of group {task} enabled               ← Flower can monitor this worker
```

**Successful ingestion trace:**
```
ingest_document_started document_id=<uuid>   ← Task picked up
Parsed 47 elements, 8 pages                  ← PDF parsed
Created 23 chunks                            ← Text chunked
Embedded 23 chunks                           ← Vectors generated
Task ...ingest_document[...] succeeded       ← Complete success
ingest_document_completed document_id=<uuid> ← Confirmation log
```

**Failed ingestion patterns:**
```
ingest_document_failed error=AuthenticationError   ← Bad API key
ingest_document_failed error=FileNotFoundError     ← Upload missing from disk
Task ...ingest_document[...] raised ...            ← Task failure with traceback
Retrying ...ingest_document[...] in 30s            ← Auto-retry (3 attempts max)
```

---

### `beat` — Celery scheduler

```bash
docker compose logs -f beat
```

**Healthy output:**
```
beat: Starting...
Scheduler: Sending due task cleanup-failed-documents (app.workers.tasks.cleanup_failed_documents)
```

The cleanup task runs every hour and marks stuck `processing` documents as `failed`.

---

### `flower` — Task queue monitor

```bash
docker compose logs -f flower
```

**Healthy output:**
```
worker: celery@<worker-id> went online.
```

If you see `went offline` repeatedly, the worker is crashing — check worker logs.

---

### `frontend` — React SPA

```bash
docker compose logs -f frontend
```

**Healthy output:**
```
Accepting connections at http://localhost:3000
```
or
```
Serving!
```

If you see errors here, the `serve` command failed. Rebuild: `docker compose up -d --build frontend`

---

### `nginx` — Reverse proxy

```bash
docker compose logs -f nginx
docker compose logs nginx --tail=50
```

**Healthy request logs (abbreviated):**
```
"POST /api/v1/auth/login HTTP/1.1" 200
"GET /api/v1/documents/ HTTP/1.1" 200
"POST /api/v1/documents/upload HTTP/1.1" 201
"GET / HTTP/1.1" 200
```

**Error patterns:**
```
connect() failed (111: Connection refused) while connecting to upstream
→ Backend or frontend container is down
→ Fix: docker compose restart backend

upstream timed out (110: Connection timed out)
→ Q&A request took too long (LLM call timeout)
→ Fix: Retry the question; check if OpenAI API is slow

"POST /api/v1/documents/upload HTTP/1.1" 422
→ Backend validation error — check backend logs for detail
```

---

### `postgres` — Database

```bash
docker compose logs -f postgres
docker compose logs postgres --tail=30
```

**Healthy startup:**
```
database system is ready to accept connections
```

**Healthy init (first run only):**
```
running "/docker-entrypoint-initdb.d/init.sql"     ← pgvector extension setup
```

**Error patterns:**
```
FATAL: password authentication failed             ← Wrong DB password in .env
FATAL: role "postgres" does not exist             ← Volume corruption — do down -v
could not open file: No such file or directory    ← Missing extension — do down -v
```

---

### `redis` — Message broker

```bash
docker compose logs -f redis
```

**Healthy startup:**
```
Ready to accept connections tcp
```

**Warning patterns:**
```
WARNING: ... maxmemory-policy is noeviction     ← Fine for dev, configure for prod
```

---

## Database Access & Queries

### Open a database session

```bash
docker compose exec postgres psql -U postgres -d pdf_qa
```

### Useful queries

```sql
-- List all tables
\dt

-- See all users
SELECT id, email, full_name, is_active, created_at
FROM users
ORDER BY created_at DESC;

-- See all documents with status
SELECT id, original_name, status, page_count, chunk_count, created_at
FROM documents
ORDER BY created_at DESC;

-- See failed documents with error
SELECT original_name, status, error_message
FROM documents
WHERE status = 'failed';

-- Count stored vector chunks
SELECT COUNT(*) AS total_chunks FROM chunks;

-- See chunks for a specific document
SELECT chunk_index, page_number, LEFT(content, 80) AS preview
FROM chunks
WHERE document_id = '<paste-document-id>'
ORDER BY chunk_index;

-- Check vector dimension stored
SELECT id, array_length(embedding::real[], 1) AS dims
FROM chunks LIMIT 3;

-- See documents for a user
SELECT d.original_name, d.status, d.chunk_count
FROM documents d
JOIN users u ON u.id = d.owner_id
WHERE u.email = 'demo@example.com';

-- Reset a user password (get hash from Python first)
UPDATE users
SET hashed_password = '<bcrypt-hash>'
WHERE email = 'user@example.com';

-- Delete a user and all their data (CASCADE handles documents + chunks)
DELETE FROM users WHERE email = 'test@example.com';
```

### Generate a bcrypt hash (to reset a password)

```bash
docker compose exec backend python -c "
from app.core.security import hash_password
print(hash_password('YourNewPassword123!'))
"
# Copy the output, then paste into the UPDATE query above
```

### Exit psql

```sql
\q
```

---

## Redis Inspection

```bash
# Open Redis CLI
docker compose exec redis redis-cli

# Check all databases
INFO keyspace

# Count pending tasks in Celery broker (db 1)
SELECT 1
LLEN celery

# Count active task results (db 2)
SELECT 2
DBSIZE

# Exit
QUIT
```

---

## Flower Task Monitor

Flower provides a full web UI for Celery task management.

### Access

Open: http://localhost:5555

### Tabs explained

**Dashboard**
- Total tasks processed (all time and today)
- Worker pool status and concurrency
- Task rate graph (tasks per minute)

**Tasks**
- Full list of every task with state: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`, `RETRY`
- Click any row to see full detail: arguments, result, traceback
- Filter by: task name = `app.workers.tasks.ingest_document`
- Sort by: `started`, `succeeded`, `failed` timestamp

**Workers**
- `pdf_qa_worker` — shows last heartbeat, pool type (threads), concurrency
- If worker shows `offline`, run: `docker compose restart worker`

**Broker**
- Queue name: `ingestion` — shows message count
- If message count keeps growing, the worker is stuck — restart it

**Monitor**
- Real-time event stream as tasks are submitted and complete

### Debugging a failed document with Flower

1. Go to http://localhost:5555/tasks
2. Filter **State = FAILURE**
3. Click the failed task row
4. Expand **Traceback** section
5. The full Python traceback shows the exact error
6. Common fix: update `.env`, then `docker compose down && docker compose up -d`

---

## Swagger UI Testing

Swagger UI at http://localhost/docs provides interactive API testing directly in the browser.

### Steps to use Swagger

**Step 1 — Authenticate**
1. Scroll down to `POST /api/v1/auth/login`
2. Click **Try it out**
3. In the **Request body** field, fill in:
   ```
   username: demo@example.com
   password: Demo1234!
   ```
4. Click **Execute**
5. From the response, copy the full `access_token` value

**Step 2 — Authorize all requests**
1. Click the **Authorize** button (top right, lock icon)
2. In the `Value` field, type: `Bearer eyJ...` (your token)
3. Click **Authorize** then **Close**

**Step 3 — Test endpoints**

| Endpoint | What to test |
|----------|-------------|
| `GET /api/v1/auth/me` | Returns your user profile |
| `POST /api/v1/documents/upload` | Upload a PDF via the file picker |
| `GET /api/v1/documents/` | Lists all your documents |
| `POST /api/v1/qa/ask` | Ask a question — fill in `question` and `document_ids` |
| `DELETE /api/v1/documents/{document_id}` | Delete a document by ID |

**Step 4 — Test Q&A in Swagger**
1. Open `POST /api/v1/qa/ask` → **Try it out**
2. Paste this into the request body:
   ```json
   {
     "question": "What are the key points in this document?",
     "document_ids": ["paste-your-doc-id-here"],
     "top_k": 5,
     "use_reranker": true
   }
   ```
3. Click **Execute**
4. The response shows `answer`, `citations`, and `confidence`

---

## Applying Code Changes

### Backend Python changes

Backend mounts `./backend` as a volume — Python code changes take effect on restart (no rebuild):

```bash
docker compose restart backend worker
```

### Frontend TypeScript/React changes

Frontend is built at image build time — requires a rebuild:

```bash
docker compose up -d --build frontend
```

### Environment variable changes

Must do a full stop + start (not just restart):

```bash
docker compose down
docker compose up -d
```

### Database model changes

After editing SQLAlchemy models, create and apply a migration:

```bash
# Generate migration
docker compose exec backend alembic revision --autogenerate -m "description_of_change"

# Apply migration
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current
```

---

## Common Operations

### View all container resource usage

```bash
docker stats
```

### Execute a command inside a container

```bash
docker compose exec backend bash         # shell in backend
docker compose exec backend python       # Python REPL
docker compose exec postgres bash        # shell in postgres
docker compose exec redis redis-cli      # Redis CLI
```

### Copy a file into a container

```bash
docker cp local-file.pdf pdf_qa_backend:/app/uploads/
```

### View container networking

```bash
docker compose exec backend curl http://postgres:5432   # test backend→postgres reach
docker compose exec backend curl http://redis:6379      # test backend→redis reach
```

### Scale workers (process more PDFs in parallel)

```bash
docker compose up -d --scale worker=3
```

### Hard reset — wipe everything and start fresh

```bash
docker compose down -v              # removes containers AND volumes (all data gone)
docker compose up -d --build        # rebuild and restart
# Re-register your account
# Re-upload your documents
```

---

## All Known Issues & Fixes

| # | Symptom | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | File upload returns `422 Unprocessable Entity` | Axios default `Content-Type: application/json` header overrode the multipart/form-data boundary | Removed default Content-Type from `axios.create()` in `frontend/src/api/client.ts` |
| 2 | Login/registration blocked when accessing via `http://localhost` | `ALLOWED_ORIGINS` list didn't include `http://localhost` (port 80) | Added `http://localhost`, `http://localhost:80`, `http://127.0.0.1` to `ALLOWED_ORIGINS` in `.env` |
| 3 | HNSW index creation fails on startup | `pgvector` maximum HNSW index dimensions is 2000; config defaulted to 3072 | Fixed `embedding_dimension` default to `1536` in `config.py` and `alembic/versions/001_initial.py` |
| 4 | Login returns `422` from the frontend form | FastAPI's `OAuth2PasswordRequestForm` requires `application/x-www-form-urlencoded`, not JSON | `authApi.login` uses `URLSearchParams` which sets the correct Content-Type |
| 5 | Celery worker crashes with asyncio event loop error | `asyncio.run()` in tasks + `@lru_cache` on async `AsyncOpenAI` client create conflicting event loops | Tasks use `asyncio.run()` for the coroutine; removed `@lru_cache` from async clients |
| 6 | Q&A always returns "outside scope of documents" | Supervisor LLM prompt was too aggressive about routing to `fallback` | Supervisor system prompt updated: defaults to `retrieval` unless clearly off-topic |
| 7 | `ValueError: invalid salt` on login (bcrypt) | `passlib 1.7.4` is incompatible with `bcrypt >= 4.0` | Replaced passlib with direct `bcrypt 4.2.1` in `security.py` |
| 8 | Frontend API calls go to `localhost:8000` (hardcoded) bypassing nginx | `VITE_API_URL` was set to `http://localhost:8000` in `docker-compose.yml` | Removed `VITE_API_URL` from `docker-compose.yml`; frontend now uses relative URLs (`/api/v1`) routing through nginx |
| 9 | `DocumentIngestionState` NameError in worker | `from __future__ import annotations` makes type hints lazy strings; LangGraph resolves them from module globals but import was inside a function | Moved `DocumentIngestionState` import to module level in `graph.py` |
| 10 | `allowed_origins` parse error crashes all containers on start | `pydantic-settings v2` requires JSON array format for `list[str]` env vars | `ALLOWED_ORIGINS` set as JSON: `["http://...","http://..."]` |
