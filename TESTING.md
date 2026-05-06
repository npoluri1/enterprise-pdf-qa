# Testing Guide

## Overview

| Layer | Framework | Location | Run With |
|-------|-----------|----------|----------|
| Backend unit + integration | pytest + pytest-asyncio | `backend/tests/` | `make test` |
| Frontend component | Vitest + React Testing Library | `frontend/src/__tests__/` | `npm test` |
| E2E | (not yet configured) | — | — |

---

## Backend Tests

### Setup

```bash
cd backend

# Install test deps (included in requirements.txt)
pip install pytest pytest-asyncio httpx pytest-cov

# Run all tests
pytest tests/ -v --cov=app --cov-report=term-missing

# Run a single file
pytest tests/test_auth.py -v

# Run by keyword
pytest -k "test_upload" -v

# Stop on first failure
pytest tests/ -x
```

### Test Database

Tests use a separate in-memory or test PostgreSQL database. Never run tests against the production database.

Configure in `backend/tests/conftest.py`:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.main import app
from app.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/pdf_qa_test"

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def client(db_engine):
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

### Test Structure

```
backend/tests/
├── conftest.py          Fixtures: db_engine, db_session, client, test_user, auth_headers
├── test_auth.py         Register, login, /me endpoint, invalid credentials
├── test_documents.py    Upload, list, delete, status polling
├── test_qa.py           /ask, /ask/stream, empty document_ids, question validation
├── test_rag/
│   ├── test_embeddings.py   Embedder output shape, determinism
│   ├── test_retriever.py    Hybrid retrieval, RRF fusion
│   └── test_pipeline.py     End-to-end RAG with mock LLM
├── test_agents/
│   └── test_graph.py        LangGraph node unit tests, state transitions
└── test_workers/
    └── test_tasks.py        Celery task with mocked embedder + DB
```

### Writing Tests

#### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_register(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "StrongPass123!"
    })
    assert response.status_code == 201
    assert "id" in response.json()
```

#### Mocking External APIs

Always mock OpenAI, Anthropic, and Unstructured in tests — never call live APIs in CI.

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ask_question(client, auth_headers, mock_documents):
    with patch("app.rag.embeddings.OpenAIEmbeddings.aembed_query",
               new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        with patch("app.agents.graph.ChatOpenAI") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=...)

            response = await client.post(
                "/api/v1/qa/ask",
                headers=auth_headers,
                json={"question": "What is this document about?", "document_ids": [...]}
            )
    assert response.status_code == 200
    assert "answer" in response.json()
```

#### Testing File Upload

```python
import io

@pytest.mark.asyncio
async def test_upload_pdf(client, auth_headers):
    pdf_content = b"%PDF-1.4 minimal test content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    response = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files=files
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
```

---

## Frontend Tests

### Setup

```bash
cd frontend
npm install   # installs vitest, @testing-library/react, jsdom
npm test      # runs vitest
npm run coverage  # coverage report
```

### Test Structure

```
frontend/src/
├── __tests__/
│   ├── components/
│   │   ├── PDFUpload.test.tsx
│   │   ├── DocumentList.test.tsx
│   │   ├── ChatInterface.test.tsx
│   │   └── CitationPanel.test.tsx
│   ├── pages/
│   │   ├── LoginPage.test.tsx
│   │   └── DashboardPage.test.tsx
│   └── hooks/
│       └── (hook tests when hooks are added)
└── setupTests.ts    @testing-library/jest-dom matchers
```

### Writing Component Tests

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatInterface } from '@/components/ChatInterface'

const createWrapper = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

test('submits question on form submit', async () => {
  const mockAsk = vi.fn().mockResolvedValue({ answer: 'Test answer', citations: [] })
  render(<ChatInterface onAsk={mockAsk} selectedDocs={[]} />, { wrapper: createWrapper() })

  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is this?' } })
  fireEvent.submit(screen.getByRole('form'))

  await waitFor(() => expect(mockAsk).toHaveBeenCalledWith('What is this?'))
})
```

---

## Coverage Requirements

| Module | Minimum Coverage |
|--------|-----------------|
| `app/api/` | 85% |
| `app/core/` | 90% |
| `app/rag/` | 75% |
| `app/agents/` | 70% |
| `app/workers/` | 70% |
| `app/models/` | 60% |
| Overall `app/` | 70% |

Check coverage:
```bash
pytest tests/ --cov=app --cov-report=html
# Open htmlcov/index.html
```

---

## Test Categories

Mark tests with pytest markers for selective runs:

```python
# In conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast unit tests, no external deps")
    config.addinivalue_line("markers", "integration: tests that need DB or Redis")
    config.addinivalue_line("markers", "slow: tests that take > 1 second")
```

```python
@pytest.mark.unit
async def test_rrf_fusion(): ...

@pytest.mark.integration
async def test_upload_and_query(): ...
```

```bash
pytest -m unit          # fast tests only
pytest -m integration   # integration tests only
pytest -m "not slow"    # skip slow tests
```

---

## CI Test Requirements

Before a PR can be merged:
- [ ] All tests pass (`make test`)
- [ ] No new test failures introduced
- [ ] Coverage does not drop below thresholds
- [ ] No live API calls in test suite (checked by mock usage)
- [ ] `pytest -m unit` completes in < 30 seconds

---

## What to Test

### Always Test

- All API endpoint happy paths (200/201 responses)
- All API endpoint error paths (400, 401, 403, 404, 422)
- JWT validation (missing token, expired token, malformed token)
- File upload validation (wrong MIME type, oversized file)
- Document ownership (user A cannot access user B's documents)

### Test with Mocks

- LLM API calls (OpenAI, Anthropic) — mock responses
- Unstructured.io PDF parsing — return fixture chunks
- Celery tasks — call the task function directly (not via broker) with mocked dependencies
- Embedder — return deterministic fake vectors

### Do Not Test

- Third-party library internals (SQLAlchemy, Pydantic, LangGraph)
- Docker Compose wiring — that's integration/E2E territory
- Nginx routing configuration
