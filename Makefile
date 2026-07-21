# WatsonX ScrumMaster Agent — PoC

.DEFAULT_GOAL := help

.PHONY: help install lint typecheck up down mock mock-fast ci

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

# ── Infrastructure (optional — not needed for make mock) ──────────────────────

up: ## Start Redis Stack via Docker Compose
	cp -n docker-compose.override.yml.example docker-compose.override.yml 2>/dev/null || true
	docker compose up -d redis

down: ## Stop all infra containers
	docker compose down

# ── Demo — zero infra required ────────────────────────────────────────────────

mock: ## Run the full pipeline in mock mode (no Redis/WatsonX/Slack needed)
	uv run python scripts/run_mock.py

mock-fast: ## Mock run with no delay (CI smoke test)
	uv run python scripts/run_mock.py --delay 0

# ── CI ────────────────────────────────────────────────────────────────────────

ci: lint typecheck ## CI gate: lint + typecheck
