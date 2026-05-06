.PHONY: up down down-v build logs shell migrate migration test test-unit test-integration \
        lint type-check coverage audit dev clean

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

down-v:
	docker compose down -v

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

restart:
	docker compose restart backend worker

# ── DB migrations ─────────────────────────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migration:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

downgrade:
	docker compose exec backend alembic downgrade -1

db-history:
	docker compose exec backend alembic history --verbose

# ── Dev shell ─────────────────────────────────────────────────────────────────
shell:
	docker compose exec backend bash

psql:
	docker compose exec postgres psql -U postgres -d pdf_qa

redis-cli:
	docker compose exec redis redis-cli

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	docker compose exec backend pytest tests/ -v --tb=short

test-unit:
	docker compose exec backend pytest tests/ -m "unit" -v --tb=short

test-integration:
	docker compose exec backend pytest tests/ -m "integration" -v --tb=short

test-frontend:
	cd frontend && npm run test

coverage:
	docker compose exec backend pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
	@echo "HTML report: backend/htmlcov/index.html"

# ── Lint & type checking ──────────────────────────────────────────────────────
lint:
	docker compose exec backend ruff check app/ tests/
	docker compose exec backend ruff format --check app/ tests/
	cd frontend && npm run lint

lint-fix:
	docker compose exec backend ruff check --fix app/ tests/
	docker compose exec backend ruff format app/ tests/

type-check:
	docker compose exec backend mypy app/
	cd frontend && npm run type-check

# ── Security ─────────────────────────────────────────────────────────────────
audit:
	docker compose exec backend pip-audit -r requirements.txt
	cd frontend && npm audit

# ── Quick start (dev) ─────────────────────────────────────────────────────────
dev: up-build migrate
	@echo ""
	@echo "  App:       http://localhost"
	@echo "  API docs:  http://localhost/docs"
	@echo "  Flower:    http://localhost:5555"
	@echo "  Metrics:   http://localhost/metrics"
	@echo ""

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf backend/htmlcov backend/.coverage backend/coverage.xml 2>/dev/null; true
	rm -rf frontend/dist frontend/coverage 2>/dev/null; true
