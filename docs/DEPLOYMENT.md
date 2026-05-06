# Deployment Guide

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- `openssl` (for generating SECRET_KEY)
- API keys: OpenAI and/or Anthropic

---

## Development

```bash
cp .env.example .env
# Edit .env — minimum required: SECRET_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY

make up        # start all 8 containers
make logs      # tail logs

# Access
# App:     http://localhost
# API docs: http://localhost/docs
# Flower:  http://localhost:5555
```

---

## Production

### 1. Prepare Secrets

```bash
# Generate a strong SECRET_KEY
openssl rand -hex 32

# Generate a strong DB password
openssl rand -base64 24
```

### 2. Configure .env

```bash
APP_ENV=production
SECRET_KEY=<output from openssl rand -hex 32>
POSTGRES_PASSWORD=<strong password>
POSTGRES_USER=pdf_qa_user
ALLOWED_ORIGINS=["https://your-domain.com"]

OPENAI_API_KEY=sk-...          # or ANTHROPIC_API_KEY
PRIMARY_LLM=openai

EMBEDDING_DIMENSION=1536       # MUST be 1536, not 3072

# Disable debug endpoints
# (see Step 4 for nginx config to block /docs, /metrics)
```

### 3. Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend alembic upgrade head
```

### 4. Production Nginx Hardening

Add to `nginx/nginx.conf` for production:

```nginx
# Block Swagger UI and ReDoc in production
location /docs { return 404; }
location /redoc { return 404; }
location /openapi.json { return 404; }

# Block Prometheus metrics from public access
location /metrics { return 404; }

# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://backend:8000;
}

# Restrict Flower to internal network
# Do not expose port 5555 in docker-compose.prod.yml
```

### 5. Security Checklist

Run through [SECURITY.md](../SECURITY.md) production checklist before going live.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `development` | `development` / `staging` / `production` |
| `SECRET_KEY` | **Yes** | weak default | JWT signing key — 32+ random chars |
| `OPENAI_API_KEY` | If using OpenAI | `""` | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | `""` | Anthropic API key |
| `PRIMARY_LLM` | No | `openai` | `openai` or `anthropic` |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model ID |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Anthropic model ID |
| `EMBEDDING_PROVIDER` | No | `openai` | `openai` or `huggingface` |
| `EMBEDDING_DIMENSION` | No | `3072` | **Set to `1536`** — 3072 exceeds pgvector limit |
| `OPENAI_EMBEDDING_MODEL` | No | `text-embedding-3-large` | OpenAI embedding model |
| `HF_EMBEDDING_MODEL` | No | `BAAI/bge-large-en-v1.5` | HuggingFace model |
| `RERANKER_MODEL` | No | `cross-encoder/ms-marco-MiniLM-L-12-v2` | Reranker model |
| `CHUNK_SIZE` | No | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | No | `64` | Overlap between chunks |
| `RETRIEVAL_TOP_K` | No | `20` | Candidates before reranking |
| `FINAL_TOP_K` | No | `5` | Results after reranking |
| `HYBRID_ALPHA` | No | `0.7` | Dense weight (1.0=pure dense, 0.0=pure BM25) |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Max PDF size in MB |
| `POSTGRES_HOST` | No | `postgres` | DB hostname (Docker service name) |
| `POSTGRES_PORT` | No | `5432` | DB port |
| `POSTGRES_USER` | No | `postgres` | DB user |
| `POSTGRES_PASSWORD` | No | `postgres` | **Change in production** |
| `POSTGRES_DB` | No | `pdf_qa` | DB name |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection (app cache) |
| `CELERY_BROKER_URL` | No | `redis://redis:6379/1` | Celery broker |
| `CELERY_RESULT_BACKEND` | No | `redis://redis:6379/2` | Celery results |
| `ALLOWED_ORIGINS` | No | `["http://localhost:3000"]` | CORS whitelist — JSON array |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LANGCHAIN_TRACING_V2` | No | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | If tracing | `""` | LangSmith API key |
| `LANGCHAIN_PROJECT` | No | `enterprise-pdf-qa` | LangSmith project name |
| `UNSTRUCTURED_API_KEY` | No | `""` | Unstructured.io cloud API key |

---

## Migrations

```bash
# Apply all pending migrations
make migrate
# or:
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current

# Create new migration after model change
make migration msg="add_page_count_index"

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

**Warning**: Changing `EMBEDDING_DIMENSION` requires:
1. Dropping and recreating the HNSW index on `chunks.embedding`
2. Re-ingesting all documents (re-embedding with new dimension)

---

## Scaling

### Celery Workers

Scale ingestion workers independently:

```bash
docker compose up -d --scale worker=4
```

Worker count should match your LLM API rate limits and CPU count.

### Database

For high traffic, consider:
- Connection pooling (PgBouncer in front of PostgreSQL)
- Read replicas for vector search
- Separate pgvector index tuning: `m` and `ef_construction` in migration

### Redis

Redis is used for Celery broker (db1), results (db2), and app cache (db0). For production, use a Redis cluster or managed Redis (Redis Cloud, AWS ElastiCache).

---

## Monitoring

| Service | URL | Credentials |
|---------|-----|-------------|
| Flower (Celery) | `http://localhost:5555` | None (add auth for prod) |
| Prometheus metrics | `http://localhost/metrics` | None (restrict for prod) |
| Swagger UI | `http://localhost/docs` | None (disable for prod) |
| LangSmith (optional) | `https://smith.langchain.com` | `LANGCHAIN_API_KEY` |

### Health Check

```bash
curl http://localhost/health
# {"status":"ok","env":"production"}
```

---

## Backup

### Database

```bash
# Backup
docker compose exec postgres pg_dump -U postgres pdf_qa > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U postgres pdf_qa < backup_20250101.sql
```

### Uploads

Backup the `backend/uploads/` volume — it contains the original PDFs. Map to a persistent storage path in `docker-compose.prod.yml`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Backend crashes on startup | `EMBEDDING_DIMENSION=3072` exceeds pgvector limit | Set `EMBEDDING_DIMENSION=1536` |
| Worker exits immediately | asyncio event loop conflict | Check `tasks.py` uses `asyncio.run()` not `@lru_cache` |
| Login 422 error | Wrong Content-Type | Use `application/x-www-form-urlencoded` |
| Upload 422 error | Axios content-type boundary | Remove explicit `Content-Type` header |
| CORS blocked | `ALLOWED_ORIGINS` format | Use JSON: `["https://domain.com"]` |
| DB connection refused | Wrong host | Use `postgres` (Docker service name), not `localhost` |
| HNSW index error | Dimension mismatch | `EMBEDDING_DIMENSION` must match existing index |
| bcrypt error | Wrong library | Use `bcrypt==4.2.1` directly; remove `passlib` |
