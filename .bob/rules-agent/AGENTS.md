# AGENTS.md — Agent (coding) mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Coding Rules

### Always `uv run` — never bare `python`
All scripts must be invoked as `uv run python <file>` to pick up the workspace virtualenv and intra-monorepo package installs.

### `_build_pipeline()` exists in TWO places — keep them in sync
`scripts/run_mock.py:_build_pipeline()` and `mcp_server.py:_build_pipeline()` are separate copies. Adding/removing a processor requires editing **both**.

### Processors receive events by value — `AgentEvent` is frozen
`model_config = {"frozen": True}` on `AgentEvent`. Never try to set attributes on an event inside a processor. Return enrichments via `ProcessorResult.enrichments` instead.

### Type-hint processors against Protocol, not concrete class
```python
# ✅ Correct
def __init__(self, watsonx: WatsonxClientProtocol) -> None: ...

# ❌ Wrong — forces ibm_watsonx_ai import in mock mode
def __init__(self, watsonx: WatsonxClient) -> None: ...
```

### `ProcessorResult` with no-op return
When a processor doesn't handle an event type, return `ProcessorResult()` (empty dataclass defaults). Never return `None`.

### MCP tool functions must be `async` (except list_* helpers)
`run_mock_pipeline`, `run_phase`, `get_sprint_snapshot`, `sync_github_project`, `get_github_project`, `analyze_sprint_activity` are all `async def`. Sync tools (`list_event_types`, `list_processors`) are plain `def`.

### No test framework — validate with `make ci`
There are no pytest/unittest files. The only validation gate is `make ci` (ruff + mypy strict). Run it before committing.

### `from __future__ import annotations` is required in every file
Needed for forward references under mypy strict + Python 3.11 target.

### Fixture-driven integration testing
To add new fixture-based scenarios, edit files in `fixtures/`. `MockSprintContextStore` auto-loads them at construction. Fixture JSON is keyed by `sprint_id` (e.g. `"SPRINT-42"`).
