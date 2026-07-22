# AGENTS.md — Plan mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Architectural Constraints

### Processors are stateless by design — the store is the only state
All `BaseProcessor` subclasses must remain stateless. The `SprintContextStoreProtocol` is the sole state sink. Hidden assumption: `ProcessingPipeline` can be constructed fresh per-request (MCP tools do this) because processors carry no session state.

### Pipeline is fail-open — processor failures are silently swallowed
`ProcessingPipeline.run()` logs exceptions per-processor but continues. Any new processor must not assume prior processors succeeded. This is intentional ("tighten later" comment in source) but is a design risk for production.

### Two separate pipeline bootstrap sites — architectural duplication
`scripts/run_mock.py:_build_pipeline()` and `mcp_server.py:_build_pipeline()` are not shared. Any structural change to the processor list requires updating both. No DRY refactor has been done here by design (PoC stage).

### Protocol isolation prevents cross-package coupling
Concrete implementations (`WatsonxClient`, real Redis store) are intentionally never imported by processors. This boundary is load-bearing: swapping mock → live requires changing only the bootstrap site, not any processor.

### `AgentEvent` immutability prevents enrichment via mutation
Enrichments from processors flow back through `ProcessorResult.enrichments`, not by modifying the event. The dispatcher receives side-effects as plain dicts — not typed objects — making the dispatcher/processor boundary intentionally loose.

### MCP server is stateless per-call
Each MCP tool call creates a fresh `MockSprintContextStore` and `ProcessingPipeline`. There is no shared state between calls. Sprint context accumulates only within a single tool invocation, not across calls.

### No Redis dependency in mock/dev path
`MockSprintContextStore` is fully in-memory and pre-seeded from `fixtures/`. Redis Stack is only required for production (`make up`). Any new feature that requires Redis in dev violates this constraint.

### `mypy_path` in `pyproject.toml` is required for the monorepo to type-check
Each workspace package root is listed in `[tool.mypy] mypy_path`. Adding a new package requires adding its source root there, otherwise mypy cannot resolve intra-monorepo imports.
