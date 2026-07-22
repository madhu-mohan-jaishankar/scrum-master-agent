# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack
Python 3.12 monorepo managed by **uv workspaces** (`pyproject.toml` at root). No test suite — validation is lint + typecheck only.

## Commands
```bash
make install      # uv sync --all-packages (one-time)
make lint         # uv run ruff check .
make format       # uv run ruff format .
make typecheck    # uv run mypy packages/ services/
make mock         # full demo — no credentials needed
make mock-fast    # mock with --delay 0 (CI smoke test)
make ci           # lint + typecheck gate
```

Run a single file directly: `uv run python <path>` — always prefix with `uv run`.  
There are **no tests**; CI gate is `make ci` (lint + typecheck).

## Code Style
- **Line length**: 100 (ruff)
- **Target**: Python 3.11 syntax (ruff), mypy runs at 3.12 strict
- **Ruff rule sets**: E, F, I (isort), UP (pyupgrade)
- **All files begin with** `from __future__ import annotations`
- **Import order** (enforced by isort): stdlib → third-party → intra-monorepo packages (each `scrumagent_*` namespace)
- **mypy strict mode** — all public functions must have full type annotations; `ignore_missing_imports = true`

## Architecture — Critical Patterns

### Processors are stateless
All processors in `packages/processors/` extend [`BaseProcessor`](packages/processors/scrumagent_processors/base.py) and must be **stateless**. State lives exclusively in `SprintContextStoreProtocol`. Breaking this assumption breaks the pipeline's fail-open retry model.

### Protocol / Mock pairs — never import the concrete class
Each integration has a Protocol + Mock pair:
- `WatsonxClientProtocol` / `MockWatsonxClient` — `packages/watsonx_client/`
- `SprintContextStoreProtocol` / `MockSprintContextStore` — `packages/context_store/`

Processors and the pipeline **type-hint against the Protocol only**, not the concrete class. This avoids importing `ibm_watsonx_ai` or Redis in mock mode.

### AgentEvent is frozen
[`AgentEvent`](packages/shared/scrumagent_shared/events.py) is a Pydantic model with `model_config = {"frozen": True}`. Never mutate it — create a new instance instead.

### Single source of truth for events
`packages/shared/scrumagent_shared/events.py` owns `AgentEvent`, `EventType`, and `EventSource`. Nothing downstream imports vendor-specific webhook types.

### MCP server logging must go to stderr
In [`mcp_server.py`](mcp_server.py), `logging.basicConfig(level=logging.WARNING, stream=sys.stderr)` is mandatory — any logging to stdout corrupts the STDIO MCP protocol channel.

### Fixture files drive mock mode
`MockSprintContextStore` pre-seeds from `fixtures/` at construction time. The fixture files (`events.json`, `snapshots.json`, `sprint.json`, etc.) are the single source of test data for both `make mock` and MCP tool calls.

### Pipeline fail-open
[`ProcessingPipeline.run()`](services/worker/worker/pipeline.py) catches per-processor exceptions and logs them but continues to the next processor. This is intentional for early-dev observability — don't change to fail-fast without discussion.

## Package Naming
| Import prefix | Package directory |
|---|---|
| `scrumagent_shared` | `packages/shared/` |
| `scrumagent_watsonx` | `packages/watsonx_client/` |
| `scrumagent_context_store` | `packages/context_store/` |
| `scrumagent_processors` | `packages/processors/` |
| `scrumagent_dispatcher` | `packages/dispatcher/` |
| `worker` | `services/worker/worker/` |

## MCP Server
`mcp_server.py` (root) uses `mcp.server.fastmcp.FastMCP`. Run via `uv run python mcp_server.py` (transport: stdio). Bob MCP config is at [`.bob/mcp.json`](.bob/mcp.json) using `${workspaceFolder}`.

## Adding a New Processor
1. Create `packages/processors/scrumagent_processors/<name>.py`, extend `BaseProcessor`.
2. Return `ProcessorResult(enrichments={...}, side_effects=[...])`.
3. Register in both `scripts/run_mock.py` and `mcp_server.py` `_build_pipeline()` functions (they are separate — both must be updated).
