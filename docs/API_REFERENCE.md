# API Reference

Base URL: `http://localhost/api/v1`
Interactive docs: `http://localhost/docs` (Swagger UI), `http://localhost/redoc`

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

---

## Authentication

### POST /auth/register

Create a new user account.

**Request** `application/json`
```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Errors**
- `400` — email already registered
- `422` — invalid email format or password too short

---

### POST /auth/login

Obtain a JWT access token.

**Request** `application/x-www-form-urlencoded` ⚠️ (not JSON)
```
username=user@example.com&password=StrongPass123!
```

**Response** `200 OK`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors**
- `401` — incorrect credentials
- `422` — missing fields

---

### GET /auth/me

Get the currently authenticated user.

**Response** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Errors**
- `401` — missing or invalid token

---

## Documents

### POST /documents/upload

Upload a PDF for ingestion. Processing is async — poll status via GET.

**Request** `multipart/form-data` ⚠️ Do not set Content-Type manually — let the client set it.
```
file: <PDF binary>
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "filename": "report.pdf",
  "status": "pending",
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Document Status Values**

| Status | Meaning |
|--------|---------|
| `pending` | Queued for ingestion |
| `processing` | Celery worker is ingesting |
| `ready` | Ingested and available for Q&A |
| `failed` | Ingestion failed — see logs |

**Errors**
- `400` — file is not a PDF or exceeds size limit
- `401` — unauthorized
- `413` — file too large (> `MAX_UPLOAD_SIZE_MB`)

---

### GET /documents/

List all documents owned by the current user.

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "filename": "report.pdf",
    "status": "ready",
    "page_count": 12,
    "chunk_count": 48,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### DELETE /documents/{id}

Delete a document and all its chunks.

**Response** `204 No Content`

**Errors**
- `403` — document belongs to another user
- `404` — document not found

---

## Q&A

### POST /qa/ask

Ask a question against selected documents. Uses the LangGraph multi-agent pipeline.

**Request** `application/json`
```json
{
  "question": "What are the main risks identified in the report?",
  "document_ids": ["uuid-1", "uuid-2"]
}
```

**Response** `200 OK`
```json
{
  "answer": "The main risks identified include...",
  "citations": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "report.pdf",
      "page_number": 4,
      "text": "The key risks are...",
      "score": 0.92
    }
  ],
  "confidence": 0.87,
  "query_expansions": [
    "What risks are mentioned in the document?",
    "Risk factors discussed in the report",
    "Identified threats and vulnerabilities"
  ]
}
```

**Errors**
- `400` — empty question or no document_ids provided
- `401` — unauthorized
- `404` — one or more document_ids not found or not owned by user
- `422` — document not ready (status != "ready")

---

### POST /qa/ask/mcp

Ask a question using Claude with MCP tool-use (agentic mode). Claude decides which documents to search.

**Request** Same as `/qa/ask`

**Response** Same shape as `/qa/ask`

**Note**: Requires `PRIMARY_LLM=anthropic` or Anthropic API key configured. Claude autonomously calls `search_documents`, `list_documents`, and `get_document_metadata` tools.

---

### GET /qa/ask/stream

Stream Q&A response as Server-Sent Events.

**Query Parameters**
```
question=<url-encoded question>
document_ids=<uuid-1>&document_ids=<uuid-2>
```

**Response** `text/event-stream`
```
data: {"type": "token", "content": "The "}
data: {"type": "token", "content": "main "}
data: {"type": "token", "content": "risks..."}
data: {"type": "citations", "citations": [...]}
data: {"type": "done"}
```

---

## Health

### GET /health

**Response** `200 OK`
```json
{"status": "ok", "env": "development"}
```

No authentication required.

---

## Prometheus Metrics

### GET /metrics

Prometheus-format metrics: HTTP request counts, latency histograms, active connections.

Returns: `text/plain` Prometheus exposition format.

---

## Error Response Format

All errors return:
```json
{
  "detail": "Human-readable error description"
}
```

For validation errors (422):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limits

No rate limiting is currently implemented. See `SECURITY.md` Known Limitations.

---

## Authentication Flow

```
1. POST /auth/register  → creates account
2. POST /auth/login     → returns {access_token}
3. Store token in client (localStorage via Zustand)
4. All requests: Authorization: Bearer <access_token>
5. Token expires after ACCESS_TOKEN_EXPIRE_MINUTES (default 60)
6. On 401: clear token, redirect to /login
```
