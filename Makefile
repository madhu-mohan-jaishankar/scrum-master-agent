# WatsonX ScrumMaster Agent — PoC

.DEFAULT_GOAL := help

.PHONY: help install lint typecheck test up down run-ingestion run-worker run-scheduler mock mock-fast ci

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────────────

install: ## Install all workspace packages with uv
	uv sync --all-packages

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Run ruff linter across the monorepo
	uv run ruff check .

format: ## Auto-format with ruff
	uv run ruff format .

typecheck: ## Run mypy across all packages and services
	uv run mypy packages/ services/

# ── Tests ─────────────────────────────────────────────────────────────────────

test: ## Run full test suite
	uv run pytest -v

# ── Infrastructure (optional — not needed for make mock) ──────────────────────

up: ## Start Redis Stack via Docker Compose
	cp -n docker-compose.override.yml.example docker-compose.override.yml 2>/dev/null || true
	docker compose up -d redis

down: ## Stop all infra containers
	docker compose down

# ── Services (optional — requires Redis + .env) ───────────────────────────────

run-ingestion: ## Run ingestion service locally
	uv run python services/ingestion/main.py

run-worker: ## Run worker service locally
	uv run python services/worker/main.py

run-scheduler: ## Run scheduler service locally
	uv run python services/scheduler/main.py

# ── Demo — zero infra required ────────────────────────────────────────────────

mock: ## Run the full pipeline in mock mode (no Redis/WatsonX/Slack needed)
	uv run python scripts/run_mock.py

mock-fast: ## Mock run with no delay (CI smoke test)
	uv run python scripts/run_mock.py --delay 0

# ── CI ────────────────────────────────────────────────────────────────────────

ci: lint typecheck test ## Full CI gate: lint + typecheck + test
