# WatsonX ScrumMaster Agent PoC

Proof of Concept for an AI-powered Scrum intelligence pipeline.
Run the demo in seconds — no Redis, no WatsonX API key, no Slack token needed.

## Demo

```bash
make install   # one-time setup
make mock      # run the full 6-phase demo
```

The demo replays a fictional sprint through the real event-processing pipeline
and prints formatted standup digests, CI alerts, and a retro brief to the console.

## What it shows

| Phase | What happens |
|---|---|
| 1 — Fixture events | GitHub PR/commit/CI events are classified by [`MockWatsonxClient`](packages/watsonx_client/scrumagent_watsonx/mock_client.py) and dispatched as alerts |
| 2 — Pre-standup brief | A scheduled trigger synthesises a sprint health brief from the in-memory store |
| 3 — Standup digests | Per-member activity summaries are formatted and "posted to Slack" (console) |
| 4 — Retro trigger | Survey responses drive a retrospective draft |
| 5 — Stale PR scan | Approved PRs open > 2 days are surfaced and nudged for merge |
| 6 — Sprint planning | Planning brief is triggered for the next sprint |

## How it works

```
fixtures/events.json
        │
        ▼
  ProcessingPipeline         services/worker/worker/pipeline.py
    ├── PRClassifierProcessor     — classifies review comments (blocking/nit/…)
    ├── CommitAnalyserProcessor   — labels commits (feature/bugfix/…)
    ├── CIMonitorProcessor        — detects CI failures and flaky pipelines
    ├── TicketTrackerProcessor    — tracks ticket lifecycle / scope creep
    ├── ActivityAggregatorProcessor — aggregates per-actor activity
    ├── CeremonySummaryProcessor  — drafts standup/retro/planning artefacts
    ├── BurndownProcessor         — tracks sprint velocity and projections
    └── ReleaseNotesProcessor     — generates grouped stakeholder release notes
        │
        ▼
  ActionDispatcher → ConsoleSink (mock) / SlackSink / JiraSink
```

AI calls use [`MockWatsonxClient`](packages/watsonx_client/scrumagent_watsonx/mock_client.py) (keyword-matching, deterministic).
Replace with [`WatsonxClient`](packages/watsonx_client/scrumagent_watsonx/protocol.py) (real `ibm-watsonx-ai`) when credentials are available.

## Bob MCP integration

The pipeline is also exposed as an **MCP server** ([`mcp_server.py`](mcp_server.py)), letting the
[Bob AI assistant](https://github.com/IBM/bob) drive the pipeline conversationally via the
**🏃 ScrumAgent** mode.

### Registered MCP tools

| Tool | Description |
|---|---|
| `run_mock_pipeline` | Run all 6 phases for a sprint — no credentials needed |
| `run_phase` | Run a single named phase (`events`, `pre_standup`, `standup`, `retro`, `stale_prs`, `sprint_planning`) |
| `get_sprint_snapshot` | Return the live sprint context as JSON |
| `list_event_types` | Enumerate all supported `EventType` values |
| `list_processors` | List the 8 processors in execution order |

### Setup

The MCP server config is at [`.bob/mcp.json`](.bob/mcp.json) and uses `${workspaceFolder}` so it
works from any checkout path:

```json
{
  "mcpServers": {
    "scrumagent": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

### ScrumAgent mode

The **🏃 ScrumAgent** custom mode (defined in [`.bob/custom_modes.yaml`](.bob/custom_modes.yaml))
wires the MCP tools to prompt templates so Bob acts as an active Scrum Master:

| Task | How Bob does it |
|---|---|
| Pre-standup brief | `get_sprint_snapshot` → fill [`prompts/pre_standup_brief.txt`](prompts/pre_standup_brief.txt) |
| Standup digest (per dev) | `run_phase(events)` → `get_sprint_snapshot` → fill [`prompts/standup_digest.txt`](prompts/standup_digest.txt) |
| Retrospective | `run_phase(retro)` → `get_sprint_snapshot` → fill [`prompts/retro_draft.txt`](prompts/retro_draft.txt) |
| Release notes | `run_phase(events)` → `get_sprint_snapshot` → fill [`prompts/release_notes.txt`](prompts/release_notes.txt) |
| Full demo | `run_mock_pipeline` |

## Repository layout

```
mcp_server.py                ← MCP server (Bob tool entrypoint)
scripts/run_mock.py          ← CLI demo entrypoint
fixtures/                    ← sample sprint, events, standup digests, retro survey
prompts/                     ← LLM prompt templates (pre_standup_brief, standup_digest,
                               retro_draft, release_notes)

packages/
  shared/                    ← AgentEvent schema (single source of truth)
  watsonx_client/            ← WatsonxClientProtocol + MockWatsonxClient
  context_store/             ← SprintContextStoreProtocol + MockSprintContextStore
  processors/                ← 8 stateless event processors
  dispatcher/                ← ActionDispatcher + ConsoleSink (+ Slack/Jira stubs)

services/worker/worker/
  pipeline.py                ← ProcessingPipeline (used by CLI and MCP server)

.bob/
  mcp.json                   ← Bob MCP server registration
  custom_modes.yaml          ← 🏃 ScrumAgent mode definition
```

## Checks

```bash
make lint      # ruff
make typecheck # mypy strict
```

## Wiring real integrations

All processors accept interfaces (`WatsonxClientProtocol`, `SprintContextStoreProtocol`).
To go live, swap the mock implementations:

1. Copy `.env.example` → `.env` and fill in credentials
2. In `scripts/run_mock.py`, replace `MockWatsonxClient()` with `WatsonxClient()`
3. For Slack/Jira output, pass `SlackSink()` / `JiraSink()` to `ActionDispatcher(mock=False, ...)`

The [technical proposal](watsonx-scrummaster-agent-technical-proposal.html) covers the full production architecture.
