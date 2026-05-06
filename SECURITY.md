# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: npoluri1@gmail.com
Subject: `[SECURITY] Enterprise PDF Q&A — <short description>`

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

Expected response time: 48 hours. We will confirm receipt, assess severity, and coordinate a fix before any public disclosure.

---

## Security Architecture

### Authentication

- **JWT (HS256)** signed with `SECRET_KEY` (must be 32+ random chars)
- Token lifetime: `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 min)
- All endpoints except `/health` and `/api/v1/auth/*` require `Authorization: Bearer <token>`
- Tokens validated in `backend/app/core/dependencies.py::get_current_user`
- **Never** accept tokens without `sub` and `exp` claims

### Password Storage

- bcrypt with default cost factor (≥12 rounds) via `bcrypt==4.2.1`
- Implementation: `backend/app/core/security.py::hash_password` / `verify_password`
- Plaintext passwords never logged, stored, or returned in any response

### File Upload Security

| Check | Implementation |
|-------|----------------|
| MIME type validation | Only `application/pdf` accepted |
| File size limit | `MAX_UPLOAD_SIZE_MB` (default 50 MB) |
| Storage location | `/app/uploads/` — outside web root, not served by nginx |
| Filename sanitization | UUIDs used as storage keys, original name stored in DB only |
| Path traversal | No user-controlled path components in file I/O |

### Database Security

- ORM (SQLAlchemy 2.0) with parameterized queries — no raw string SQL construction
- Users can only access their own documents (owner_id FK enforced in all queries)
- DB credentials in `.env` only — never hardcoded
- pgvector extension access limited to app user

### CORS

- Explicit `allowed_origins` list from `ALLOWED_ORIGINS` env var
- **Never** set `["*"]` in staging or production
- Credentials allowed only for listed origins

### LLM Prompt Security

- User-supplied question text is included in LLM prompts — treat as untrusted input
- Maximum question length enforced at API level (prevent prompt flooding)
- Retrieved document chunks are source-attributed — LLM is instructed to cite only from context
- Evaluator agent performs hallucination detection on LLM output

### Container Security

- Backend runs as non-root user inside container (add `USER appuser` to Dockerfile for prod)
- Secrets passed via environment variables, never baked into Docker images
- `.env` is gitignored and must never be committed
- Production: use Docker secrets or a secrets manager (Vault, AWS Secrets Manager) instead of `.env`

---

## Secrets Management

### Development

Use `.env` file (gitignored). Copy `.env.example` and fill in real values.

### Production Requirements

| Secret | Requirement |
|--------|-------------|
| `SECRET_KEY` | Cryptographically random, 32+ chars — `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Strong password, not the default `postgres` |
| `OPENAI_API_KEY` | Rotate if exposed; use project-scoped keys with spend limits |
| `ANTHROPIC_API_KEY` | Rotate if exposed |
| `LANGCHAIN_API_KEY` | Rotate if exposed |

**Rotation procedure**: update secret in secrets manager → redeploy containers → invalidate all active JWT tokens by rotating `SECRET_KEY`.

---

## Dependency Security

```bash
# Audit Python dependencies for known CVEs
pip install pip-audit
pip-audit -r backend/requirements.txt

# Audit Node dependencies
cd frontend && npm audit
```

All dependency versions are pinned in `requirements.txt` and `package.json`. Update with care — run full test suite after any version bump.

---

## Security Checklist (Pre-Deploy)

- [ ] `SECRET_KEY` is not the default value and is 32+ chars
- [ ] `POSTGRES_PASSWORD` is not `postgres`
- [ ] `ALLOWED_ORIGINS` does not include `*`
- [ ] `APP_ENV=production` is set
- [ ] `.env` is not committed to git
- [ ] `pip-audit` shows no critical/high CVEs
- [ ] `npm audit` shows no critical/high vulnerabilities
- [ ] Flower (`localhost:5555`) is not publicly exposed
- [ ] Prometheus metrics endpoint (`/metrics`) is not publicly exposed
- [ ] `/docs` and `/redoc` endpoints are disabled or protected in production
- [ ] Docker containers are not running as root
- [ ] Upload directory is not served as static files

---

## Known Security Limitations

1. **No rate limiting** — add nginx rate limiting or a FastAPI middleware (e.g., `slowapi`) before production
2. **No email verification** — registration accepts any email without verification
3. **No refresh token rotation** — current implementation issues non-rotating refresh tokens
4. **Flower UI has no auth** — restrict via nginx basic auth or VPN in production
5. **Prometheus `/metrics` is public** — restrict access in production nginx config
