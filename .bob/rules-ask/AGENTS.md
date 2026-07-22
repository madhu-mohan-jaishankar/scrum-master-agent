# AGENTS.md — Ask (documentation) mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context

### `scripts/run_mock.py` and `mcp_server.py` duplicate the pipeline bootstrap
The demo CLI (`scripts/run_mock.py`) and the MCP server (`mcp_server.py`) contain separate copies of `_build_pipeline()`. Documentation must note both locations when describing how the pipeline is wired.

### `services/worker/worker/pipeline.py` is the real pipeline — not a service
Despite living under `services/worker/`, `ProcessingPipeline` is a plain Python class, not a long-running service. Both the CLI demo and MCP server instantiate it directly per-request.

### `packages/watsonx_client/` contains a mock, not just the real client
`MockWatsonxClient` (keyword-matching, no API calls) lives alongside the real `WatsonxClient` stub. The mock is deterministic and used by default in all demo/MCP paths.

### `fixtures/` is the canonical data source for ALL demo modes
Mock mode, MCP tool calls, and `MockSprintContextStore` all read from `fixtures/`. There is no separate test data directory.

### `EventType` and `EventSource` use `StrEnum` (dot notation = string value)
`EventType.PR_COMMENT.value == "pr.comment"` — the `.value` form appears in JSON fixtures and log output. The enum members use `UPPER_SNAKE` but wire-format is `lower.dot.separated`.

### Phase numbering in `run_mock.py` comments is non-sequential
The print output says "Phase 7", "Phase 9", "Phase 8" — the phase labels in the console output do not match execution order. The actual execution order matches the code flow, not the labels.

### ScrumAgent Bob mode is defined in `.bob/custom_modes.yaml`
The `🏃 ScrumAgent` mode wires prompt templates from `prompts/` to MCP tool calls. Mode behaviour is documented inline in that YAML file.
