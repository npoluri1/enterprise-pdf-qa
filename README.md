# Enterprise PDF Q&A Platform

> Upload PDFs, ask questions, get **AI-generated answers with source citations** — powered by LangGraph multi-agent RAG, pgvector hybrid search, Celery async ingestion, and a React dashboard.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Setup](#first-time-setup)
3. [Starting the Application](#starting-the-application)
4. [All Access URLs](#all-access-urls)
5. [Using the Application — Step by Step](#using-the-application--step-by-step)
6. [Testing Every Feature](#testing-every-feature)
7. [Checking Logs — Every Service](#checking-logs--every-service)
8. [Monitoring Screens](#monitoring-screens)
9. [Stopping & Resetting](#stopping--resetting)
10. [Troubleshooting](#troubleshooting)
11. [Architecture](#architecture)

---

## Prerequisites

| Requirement | Minimum Version | Check |
|---|---|---|
| Docker Desktop | 24+ (Linux containers) | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| OpenAI API key | — | https://platform.openai.com/api-keys |

> No local Python or Node.js installation required — everything runs in Docker.

---

## First-Time Setup

### Step 1 — Configure your environment

The `.env` file is already present. Open it and verify these values:

```
enterprise-pdf-qa/.env
```

**Required settings to check:**

```env
OPENAI_API_KEY=sk-proj-...        # Your real OpenAI key (must have billing credits)
SECRET_KEY=change-me-...          # Change to a random 32+ character string for production
EMBEDDING_DIMENSION=1536          # Do NOT change — must match the database HNSW index
ALLOWED_ORIGINS=["http://localhost","http://localhost:80","http://localhost:3000","http://localhost:5173","http://127.0.0.1"]
```

> **Never commit `.env` to git.** It is already in `.gitignore`.

### Step 2 — Build and start all containers

```bash
cd enterprise-pdf-qa
docker compose up -d --build
```

**First run** pulls base images and installs all dependencies — takes **5–10 minutes**.
**Subsequent starts** use cached layers and take **~20 seconds**.

Watch the build progress:
```bash
docker compose logs -f
```

---

## Starting the Application

### Normal start (after first build)

```bash
docker compose up -d
```

### Start with fresh build (after code changes)

```bash
docker compose up -d --build
```

### Rebuild a single service only

```bash
docker compose up -d --build backend    # after Python changes
docker compose up -d --build frontend   # after React/TypeScript changes
docker compose up -d --build worker     # after worker changes
```

### Verify all 8 containers are running

```bash
docker compose ps
```

Expected output — every container should show `Up`:

```
NAME              STATUS                  PORTS
pdf_qa_backend    Up X minutes            0.0.0.0:8000->8000/tcp
pdf_qa_beat       Up X minutes
pdf_qa_flower     Up X minutes            0.0.0.0:5555->5555/tcp
pdf_qa_frontend   Up X minutes            0.0.0.0:3000->3000/tcp
pdf_qa_nginx      Up X minutes            0.0.0.0:80->80/tcp
pdf_qa_postgres   Up X minutes (healthy)  0.0.0.0:5432->5432/tcp
pdf_qa_redis      Up X minutes (healthy)  0.0.0.0:6379->6379/tcp
pdf_qa_worker     Up X minutes
```

**Both `postgres` and `redis` must show `(healthy)` before the backend works.**

### Quick health check

```bash
curl http://localhost/health
# Expected: {"status":"ok","env":"development"}
```

---

## All Access URLs

| Screen | URL | What You See |
|--------|-----|-------------|
| **Main Application** | http://localhost | React app — login, dashboard, chat |
| **Swagger API Docs** | http://localhost/docs | Interactive API explorer — try all endpoints |
| **ReDoc API Docs** | http://localhost/redoc | Alternative API documentation |
| **Flower (Celery UI)** | http://localhost:5555 | Task queue monitor — see PDF ingestion jobs |
| **Prometheus Metrics** | http://localhost/metrics | Raw HTTP metrics for all endpoints |
| **Backend direct** | http://localhost:8000 | Same backend, no nginx proxy |
| **Frontend direct** | http://localhost:3000 | Same React app, no nginx proxy |

---

## Using the Application — Step by Step

### Screen 1 — Login / Register page (`http://localhost`)

**To register a new account:**
1. Open http://localhost in your browser
2. Click **Register** (link at the bottom of the card)
3. Enter: Email address, Password, Full name (optional)
4. Click **Register**
5. You'll see the toast: _"Account created! Please log in."_
6. The form switches back to login mode automatically

**To log in:**
1. Enter your email and password
2. Click **Sign in**
3. You are redirected to the Dashboard

> **Existing test account:** `demo@example.com` / `Demo1234!`
> **Your account (reset):** `npoluri5@gmail.com` / `Npoluri5@2025`

---

### Screen 2 — Dashboard (`http://localhost/dashboard`)

The dashboard has three areas:

```
┌─────────────────────┬──────────────────────────────────────┐
│  LEFT SIDEBAR       │  MAIN CHAT AREA                      │
│                     │                                      │
│  [Upload Zone]      │  [Mode: LangGraph | Claude+MCP]      │
│                     │                                      │
│  [Document List]    │  [Message history]                   │
│  • doc1.pdf ✓ ready │                                      │
│  • doc2.pdf ⟳ proc  │  [Question input + Send button]     │
│                     │                                      │
│  [Selection count]  │  [Citations panel (collapsible)]     │
└─────────────────────┴──────────────────────────────────────┘
```

**Header bar:** Shows your email address and a logout button (top right).

---

### Screen 3 — Upload a PDF

1. In the left sidebar, find the **upload zone** (dashed border area)
2. Either **drag & drop** a PDF onto it, or **click** to open a file picker
3. Select one or more PDF files (max 50 MB each)
4. Toast appears: _"filename.pdf uploaded — processing…"_
5. The document appears in the list below with status badge:
   - 🟡 **pending** — queued for the Celery worker
   - 🔵 **processing** — worker is parsing, chunking, embedding
   - 🟢 **ready** — document is indexed and searchable
   - 🔴 **failed** — ingestion error (check worker logs)
6. Status updates **automatically every 3 seconds** — no manual refresh needed
7. Wait for **ready** before asking questions

> Processing time depends on PDF size and OpenAI embedding API speed. Typical: 30–90 seconds per document.

---

### Screen 4 — Ask Questions

1. Click on a **ready** document in the list to **select** it (it highlights blue)
2. You can select multiple documents to search across all of them
3. Type your question in the input box at the bottom
4. Press **Enter** or click the **Send** button (paper plane icon)
5. A loading spinner appears while the agents process your question
6. The answer appears with:
   - **Answer text** (formatted markdown with bullet points, headers, etc.)
   - **Confidence score** shown below the answer (e.g. _"openai/gpt-4o · 87% confidence"_)
   - **Sources panel** — click to expand and see the exact text excerpt from each source

**Selecting no documents** searches across all your uploaded documents.

---

### Screen 5 — Chat Modes (top bar of main area)

Two modes available:

| Mode | Button | How It Works |
|------|--------|-------------|
| **LangGraph Multi-Agent** | Blue "Bot" button | 5-agent pipeline: supervisor → expand queries → hybrid retrieval → synthesize → evaluate |
| **Claude + MCP** | Purple "Zap" button | Claude calls `search_documents` tool in an agentic loop, gathering evidence before answering |

> Claude + MCP requires `ANTHROPIC_API_KEY` to be set in `.env`.

---

### Screen 6 — Citations Panel

After each assistant answer, a **Sources** panel appears at the bottom of the message:

1. Click the **Sources (N)** header to see the list
2. Each source shows:
   - Source number badge
   - Document name and page number
   - Relevance score (e.g. _"92% match"_)
3. Click any source row to **expand** and see the exact text excerpt from that page
4. Click again to **collapse**

---

### Screen 7 — Flower Task Monitor (`http://localhost:5555`)

Flower shows all Celery background tasks:

1. Open http://localhost:5555
2. Click **Tasks** in the top nav to see all tasks
3. Each `app.workers.tasks.ingest_document` task corresponds to one PDF upload
4. States: `PENDING` → `STARTED` → `SUCCESS` / `FAILURE`
5. Click any task row to see full arguments, result, and traceback (on failure)

**Dashboard tab** shows:
- Active workers
- Task rate (tasks/second)
- Queues: `ingestion` and `qa`

---

## Testing Every Feature

### Test 1 — Health check

```bash
curl http://localhost/health
```
Expected: `{"status":"ok","env":"development"}`

---

### Test 2 — Register a new user

```bash
curl -X POST http://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@mycompany.com", "password": "SecurePass123!", "full_name": "Test User"}'
```
Expected: `201` response with `{"id":"...","email":"test@mycompany.com",...}`

---

### Test 3 — Login and get a token

```bash
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@mycompany.com&password=SecurePass123!"
```
Expected: `{"access_token":"eyJ...","token_type":"bearer"}`

Save the token:
```bash
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@example.com&password=Demo1234!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:40}..."
```

---

### Test 4 — Upload a PDF

```bash
curl -X POST http://localhost/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your-document.pdf"
```
Expected: `201` with `{"id":"...","status":"pending",...}`

---

### Test 5 — Check document status

```bash
curl http://localhost/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN"
```
Expected: `{"items":[{"id":"...","status":"ready",...}],"total":1}`

Poll until `status` changes from `processing` to `ready`.

---

### Test 6 — Ask a question

```bash
# Replace <doc-id> with the ID from Test 5
curl -X POST http://localhost/api/v1/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main topics covered in this document?",
    "document_ids": ["<doc-id>"],
    "top_k": 5,
    "use_reranker": true
  }'
```
Expected: `{"answer":"...","citations":[...],"confidence":0.85,...}`

---

### Test 7 — Verify authentication guards

```bash
# Should return 401
curl http://localhost/api/v1/documents/
curl http://localhost/api/v1/auth/me

# Should return 401 (bad token)
curl http://localhost/api/v1/documents/ \
  -H "Authorization: Bearer invalid-token"
```

---

### Test 8 — Try uploading a non-PDF file (should be rejected)

```bash
echo "this is not a pdf" > test.txt
curl -X POST http://localhost/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"
```
Expected: `400 {"detail":"Only PDF files are accepted"}`

---

### Test 9 — View Swagger UI end-to-end

1. Open http://localhost/docs
2. Click **Authorize** (top right lock icon)
3. First run `POST /auth/login` — copy the `access_token` from the response
4. Paste into the Authorize dialog as `Bearer <token>`
5. Try `POST /documents/upload` to upload a file directly from the browser
6. Try `POST /qa/ask` with your question

---

## Checking Logs — Every Service

### View all services at once

```bash
docker compose logs -f
```
Press `Ctrl+C` to stop following.

---

### Backend (FastAPI + LangGraph)

```bash
# Live tail
docker compose logs -f backend

# Last 100 lines
docker compose logs backend --tail=100

# Filter for errors only
docker compose logs backend | grep -i "error\|exception\|traceback"

# Filter for Q&A activity
docker compose logs backend | grep -i "supervisor\|retrieved\|synthesis\|confidence"
```

**What to look for in backend logs:**

| Log line | Meaning | Action |
|----------|---------|--------|
| `Application startup complete` | Backend started OK | None |
| `startup env=development` | App is running in dev mode | None |
| `GET /health 200` | Health checks passing | None |
| `POST /api/v1/auth/register 201` | User registered | None |
| `POST /api/v1/auth/login 200` | Login succeeded | None |
| `POST /api/v1/auth/login 401` | Wrong credentials | Check password |
| `POST /api/v1/documents/upload 201` | Upload accepted | None |
| `POST /api/v1/documents/upload 422` | Upload validation failed | Check Content-Type / file format |
| `POST /api/v1/qa/ask 200` | Q&A answered | None |
| `supervisor_routed route=retrieval` | Q&A going to RAG pipeline | None |
| `supervisor_routed route=fallback` | Q&A routed to fallback | Rephrase question |
| `Retrieved N chunks after reranking` | RAG retrieval succeeded | None |
| `AuthenticationError` | Invalid API key | Fix OPENAI_API_KEY in .env |
| `insufficient_quota` | OpenAI billing limit | Add credits at platform.openai.com |
| `RateLimitError` | Too many API calls | Wait and retry |

---

### Worker (Celery — PDF ingestion)

```bash
# Live tail
docker compose logs -f worker

# Last 100 lines
docker compose logs worker --tail=100

# Show only ingestion events
docker compose logs worker | grep -i "ingest\|task\|error\|celery"
```

**What to look for in worker logs:**

| Log line | Meaning | Action |
|----------|---------|--------|
| `celery@... ready` | Worker started and connected | None |
| `mingle: all alone` | Only one worker running (normal) | None |
| `ingest_document_started document_id=...` | PDF ingestion begun | None |
| `ingest_document_completed document_id=...` | Ingestion fully done — doc is `ready` | None |
| `ingest_document_failed error=...` | Ingestion error | See error message |
| `Parsed N elements, M pages` | PDF was parsed | None |
| `Created N chunks` | Text chunking done | None |
| `Embedded N chunks` | Vectors stored in DB | None |
| `Task app.workers.tasks.ingest_document[...] succeeded` | Full success | None |
| `Task ...ingest_document[...] raised ...` | Task failed | Check traceback below |
| `RetryError` | Task retried 3 times and still failing | Fix root cause, re-upload |

**Common worker failures:**

```
# OpenAI API key invalid
AuthenticationError: Error code: 401

# OpenAI quota exceeded
RateLimitError: insufficient_quota

# File not found (upload_dir missing or wrong path)
FileNotFoundError: PDF not found: /app/uploads/...

# pgvector dimension mismatch
ERROR: expected vector with dimension 1536, got 3072
→ Fix: set EMBEDDING_DIMENSION=1536 in .env, down -v, up -d
```

---

### Beat (Celery scheduler)

```bash
docker compose logs -f beat

# Expected healthy output
docker compose logs beat | grep -i "beat\|schedule\|task"
```

**What to look for:**

| Log line | Meaning |
|----------|---------|
| `beat: Starting...` | Scheduler started |
| `Scheduler: Sending due task cleanup-failed-documents` | Hourly cleanup running |

---

### Flower (Task monitor)

```bash
docker compose logs -f flower
```

Flower mostly serves its web UI. Errors here are rare.

| Log line | Meaning |
|----------|---------|
| `worker: celery@... went online` | Worker connected to broker |
| `worker: celery@... went offline` | Worker disconnected (restart it) |

---

### Frontend (React)

```bash
docker compose logs -f frontend

# Check if static files are being served
docker compose logs frontend | grep -i "error\|warn\|serving"
```

**What to look for:**

| Log line | Meaning |
|----------|---------|
| `Serving!` or `Accepting connections...` | Frontend serving correctly |
| Any `error` line | Check and report |

---

### Nginx (Reverse proxy)

```bash
docker compose logs -f nginx

# Show only errors
docker compose logs nginx | grep -i "error\|warn\|crit"

# Show all request logs
docker compose logs nginx | grep -v "GET /metrics\|GET /health"
```

**What to look for:**

| Log line | Meaning | Action |
|----------|---------|--------|
| `"POST /api/v1/... 200"` | Request proxied successfully | None |
| `"POST /api/v1/... 422"` | Backend returned validation error | Check backend logs |
| `"POST /api/v1/... 401"` | Auth failure | Check token / credentials |
| `connect() failed ... Connection refused` | Backend or frontend container down | `docker compose restart backend` |
| `upstream timed out` | Request took too long | Check backend for slow LLM calls |

---

### PostgreSQL (Database)

```bash
docker compose logs -f postgres

# Check database activity
docker compose logs postgres | grep -i "error\|warning\|fatal"
```

**Connect directly to query the database:**

```bash
# Open psql
docker compose exec postgres psql -U postgres -d pdf_qa

# Useful queries inside psql:
\dt                                          -- list all tables
SELECT email, created_at FROM users;        -- see all users
SELECT original_name, status, chunk_count FROM documents; -- see all documents
SELECT COUNT(*) FROM chunks;                -- count total stored chunks
SELECT id, status, error_message FROM documents WHERE status='failed'; -- see failures
\q                                          -- quit
```

---

### Redis (Broker)

```bash
docker compose logs -f redis

# Check Redis stats
docker compose exec redis redis-cli info server | grep redis_version
docker compose exec redis redis-cli info keyspace    # shows databases
docker compose exec redis redis-cli -n 1 llen celery # pending tasks in queue
```

**What to look for:**

| Log line | Meaning |
|----------|---------|
| `Ready to accept connections` | Redis started OK |
| `WARNING: ... maxmemory` | Redis running low on memory |

---

## Monitoring Screens

### Screen: Flower (`http://localhost:5555`)

Flower is the visual Celery task monitor. Use it to:

**Dashboard tab:**
- See total tasks processed today
- Active worker count
- Task throughput rate

**Tasks tab:**
- `State: SUCCESS` — document ingested OK
- `State: FAILURE` — ingestion failed (click row to see traceback)
- `State: STARTED` — currently being processed
- `State: PENDING` — waiting in queue
- Filter by task name: `app.workers.tasks.ingest_document`

**Workers tab:**
- Shows `pdf_qa_worker` with heartbeat timestamp
- Pool: `threads`, Concurrency: `2`
- Processed / Failed counters

**Broker tab:**
- Queue `ingestion`: active message count
- Click queue name to see queued messages

**How to use Flower to debug a stuck PDF:**
1. Open http://localhost:5555/tasks
2. Find the task for your document ID (arguments column shows `document_id`)
3. Click the task row
4. Expand **Result** or **Traceback** to see what failed

---

### Screen: Swagger UI (`http://localhost/docs`)

Swagger lets you test every API endpoint directly from the browser:

1. Open http://localhost/docs
2. Click **POST /api/v1/auth/login** → **Try it out**
3. Enter `username=demo@example.com` and `password=Demo1234!`
4. Click **Execute** — copy the `access_token` from the response
5. Click **Authorize** (top right) → paste `Bearer <token>` → click Authorize
6. Now all subsequent requests use your token automatically
7. Try:
   - **GET /api/v1/auth/me** — see your profile
   - **POST /api/v1/documents/upload** — upload a PDF
   - **GET /api/v1/documents/** — list your documents
   - **POST /api/v1/qa/ask** — ask a question

---

### Screen: Prometheus Metrics (`http://localhost/metrics`)

Raw metrics in Prometheus format. Useful for monitoring API performance:

```bash
# See all available metrics
curl -s http://localhost/metrics | grep "# HELP"

# Request counts per endpoint
curl -s http://localhost/metrics | grep http_requests_total

# Response time histograms
curl -s http://localhost/metrics | grep http_request_duration
```

Key metrics:
| Metric | Meaning |
|--------|---------|
| `http_requests_total{handler="/api/v1/qa/ask"}` | Total Q&A requests |
| `http_requests_total{status_code="422"}` | Total validation failures |
| `http_request_duration_seconds_bucket` | Latency histogram |

---

## Stopping & Resetting

### Stop all containers (keep data)

```bash
docker compose down
```
All data (users, documents, vectors) is preserved in Docker volumes.

### Restart all containers

```bash
docker compose restart
```

### Restart a single service

```bash
docker compose restart backend
docker compose restart worker
docker compose restart frontend
```

### Full reset (wipes ALL data — users, documents, vectors, uploads)

```bash
docker compose down -v
docker compose up -d
```
After this you must register a new account and re-upload all documents.

### Apply code changes without full rebuild

Backend and worker mount `./backend` as a live volume — Python changes apply on restart:
```bash
docker compose restart backend worker
```

Frontend changes require a rebuild:
```bash
docker compose up -d --build frontend
```

---

## Troubleshooting

### Problem: Cannot login — `401 Invalid credentials`

```bash
# Check if the user exists
docker compose exec postgres psql -U postgres -d pdf_qa \
  -c "SELECT email, created_at FROM users ORDER BY created_at DESC;"

# Reset a user's password
docker compose exec backend python -c "
from app.core.security import hash_password
print(hash_password('YourNewPassword123!'))
"
# Copy the hash output, then:
docker compose exec postgres psql -U postgres -d pdf_qa \
  -c "UPDATE users SET hashed_password='<paste-hash>' WHERE email='user@example.com';"
```

---

### Problem: Upload returns `422 Unprocessable Entity`

```bash
docker compose logs backend --tail=20 | grep "422\|upload"
```

Causes and fixes:
| Cause | Fix |
|-------|-----|
| Wrong file type (not PDF) | Only `.pdf` files accepted |
| File > 50 MB | Reduce file size or increase `MAX_UPLOAD_SIZE_MB` in `.env` |
| Frontend sending wrong Content-Type | The fixed `client.ts` removes the default JSON Content-Type — ensure frontend was rebuilt |

---

### Problem: Document stuck on `processing` or `failed`

```bash
# Check worker logs for the error
docker compose logs worker --tail=50

# Check what the document's error_message is
docker compose exec postgres psql -U postgres -d pdf_qa \
  -c "SELECT original_name, status, error_message FROM documents WHERE status='failed';"
```

Common causes:
| Error message | Fix |
|--------------|-----|
| `AuthenticationError` | Fix `OPENAI_API_KEY` in `.env`, restart: `docker compose restart backend worker` |
| `insufficient_quota` | Add billing credits at https://platform.openai.com/settings/billing |
| `FileNotFoundError` | Upload directory missing — ensure `uploads_data` volume is mounted |
| `expected vector with dimension N` | `EMBEDDING_DIMENSION` mismatch — see Full Reset above |

---

### Problem: Q&A returns "No relevant documents found" or "outside scope"

1. Check the document status is `ready` (not still `processing`)
2. Verify you have **selected** the document (click it in the sidebar — it should highlight blue)
3. Try selecting **all** documents (deselect to search everything)
4. Check backend logs for the actual retrieval result:

```bash
docker compose logs backend --tail=30 | grep -i "retriev\|supervisor\|chunks"
```

---

### Problem: Q&A returns error / `Request failed`

```bash
docker compose logs backend --tail=30
docker compose logs worker --tail=20
```

If you see `RateLimitError` or `insufficient_quota`:
- Add OpenAI credits at https://platform.openai.com/settings/billing
- Then restart: `docker compose restart backend worker`

---

### Problem: Container keeps restarting

```bash
# See why it's restarting
docker compose logs <service-name> --tail=40

# Check exit codes
docker compose ps
```

---

### Problem: `postgres` or `redis` not reaching `(healthy)` state

```bash
docker compose logs postgres --tail=20
docker compose logs redis --tail=20

# Force restart the unhealthy container
docker compose restart postgres
docker compose restart redis
```

If postgres is corrupt (rare): `docker compose down -v && docker compose up -d`

---

### Problem: Changes to `.env` not taking effect

Environment variables are loaded at container startup. After changing `.env`:

```bash
docker compose down
docker compose up -d
```

> `docker compose restart` alone does NOT reload `.env`.

---

## Architecture

### Service Map

```
Browser
  │
  ▼ :80
nginx (reverse proxy)
  ├── /api/*  ──►  backend:8000  (FastAPI + LangGraph)
  └── /*      ──►  frontend:3000 (React SPA)

backend:8000
  ├── /api/v1/auth/*        JWT register / login
  ├── /api/v1/documents/*   Upload → Celery task → worker
  └── /api/v1/qa/*          LangGraph graph / MCP / SSE stream

worker (Celery)
  └── ingest_document:
        PDF → pypdf/Unstructured → chunks → OpenAI embed → pgvector

postgres:5432  pgvector + pg_trgm + uuid-ossp
redis:6379     Celery broker (db1) + results (db2) + app cache (db0)
flower:5555    Celery web UI
```

### Q&A Agent Pipeline (LangGraph)

```
User question
  │
  ▼
[Supervisor]        Decides: retrieval vs. fallback
  │
  ▼
[Query Expansion]   Generates 3 diverse sub-queries
  │
  ▼
[Retrieval]         pgvector HNSW (dense) + BM25 (sparse) → RRF fusion
                    → Cross-encoder reranking (top 5 chunks)
  │
  ▼
[Synthesis]         LLM generates answer with inline citations
  │
  ▼
[Evaluator]         Confidence score (0.0–1.0)
  │
  ▼
Response: { answer, citations[], confidence }
```

### PDF Ingestion Pipeline (Celery)

```
POST /documents/upload
  → save file to /app/uploads/<uuid>.pdf
  → create Document record (status=pending)
  → enqueue Celery task

Celery worker picks up task:
  → PDFProcessor: pypdf page extraction (or Unstructured.io cloud if key set)
  → DocumentChunker: RecursiveCharacterTextSplitter (chunk_size=512, overlap=64)
  → OpenAIEmbedder: text-embedding-3-large @ 1536 dims (batched)
  → Store chunks + vectors in postgres/pgvector
  → Update Document.status = "ready"
```

### Database Tables

```sql
users      (id, email, hashed_password, full_name, is_active, created_at)
documents  (id, owner_id→users, filename, original_name, status, page_count, chunk_count, error_message, created_at)
chunks     (id, document_id→documents, content, embedding Vector(1536), chunk_index, page_number)
```

---

## Known Issues & Applied Fixes

| Issue | Root Cause | Fix Applied |
|-------|-----------|------------|
| File upload returns `422` | Axios default `Content-Type: application/json` overrides multipart boundary | Removed default Content-Type from axios instance in `client.ts` |
| Login/registration blocked from `http://localhost` | CORS `ALLOWED_ORIGINS` didn't include port-80 origin | Added `http://localhost` and `http://127.0.0.1` to `ALLOWED_ORIGINS` in `.env` |
| HNSW index creation fails | pgvector max dims = 2000; config defaulted to 3072 | Fixed default `EMBEDDING_DIMENSION=1536` in `config.py` and migration |
| Login returns `422` | FastAPI OAuth2 requires `application/x-www-form-urlencoded`, not JSON | Frontend login uses `URLSearchParams` |
| Worker crashes on asyncio loop | `@lru_cache` on async client conflicts with `asyncio.run()` in Celery | Use `asyncio.run()`, no `@lru_cache` on async clients in tasks |
| Q&A always falls back | Supervisor LLM too aggressively routing to fallback | Updated supervisor prompt to default to `retrieval` |
| bcrypt `ValueError` on login | `passlib 1.7.4` incompatible with `bcrypt>=4.0` | Replaced passlib with direct `bcrypt 4.2.1` |
