# WatsonX ScrumMaster Agent PoC

Proof of Concept for an AI-powered Scrum intelligence pipeline.
Run the demo in seconds — no Redis, no WatsonX API key, no Slack token needed.

## Demo

```bash
make install   # one-time setup
make mock      # run the full 4-phase demo
```

The demo replays a fictional sprint through the real event-processing pipeline
and prints formatted standup digests, CI alerts, and a retro brief to the console.

## What it shows

| Phase | What happens |
|---|---|
| 1 — Fixture events | GitHub PR comments and CI failures are classified by [`MockWatsonxClient`](packages/watsonx_client/scrumagent_watsonx/mock_client.py) and dispatched as alerts |
| 2 — Pre-standup brief | A scheduled trigger synthesises a sprint health brief from the in-memory store |
| 3 — Standup digests | Per-member activity summaries are formatted and "posted to Slack" (console) |
| 4 — Retro trigger | Survey responses drive a retrospective draft |

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
    └── ActivityAggregatorProcessor — aggregates per-actor activity
        │
        ▼
  ActionDispatcher → ConsoleSink (mock) / SlackSink / JiraSink
```

AI calls use [`MockWatsonxClient`](packages/watsonx_client/scrumagent_watsonx/mock_client.py) (keyword-matching, deterministic).
Replace with [`WatsonxClient`](packages/watsonx_client/scrumagent_watsonx/protocol.py) (real `ibm-watsonx-ai`) when credentials are available.

## Repository layout

```
scripts/run_mock.py          ← demo entrypoint
fixtures/                    ← sample sprint, events, standup digests, retro survey
prompts/                     ← LLM prompt templates (used by real WatsonxClient)

packages/
  shared/                    ← AgentEvent schema (single source of truth)
  watsonx_client/            ← WatsonxClientProtocol + MockWatsonxClient
  context_store/             ← SprintContextStoreProtocol + MockSprintContextStore
  processors/                ← 5 stateless event processors
  dispatcher/                ← ActionDispatcher + ConsoleSink (+ Slack/Jira stubs)

services/worker/worker/
  pipeline.py                ← ProcessingPipeline (used directly by the demo)
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
