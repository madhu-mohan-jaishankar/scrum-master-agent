# Implementation Plan: WatsonX ScrumMaster Agent — Architecture 2 (Event-Driven)

> **Scope: PoC / Demo only.**
> All processing runs in mock mode — zero external infrastructure required.
> `make mock` is the primary demo entry point.
> Real WatsonX, Slack, and Jira integrations are scaffolded behind Protocol
> interfaces and can be wired in a later phase.

## Overview

Architecture 2 is a fully event-driven intelligence pipeline. Every development
signal (GitHub webhook, Jira update, CI outcome) is normalised into a canonical
`AgentEvent`, published to a Redis Stream, processed by stateless processor
functions (which call a `WatsonxClientProtocol` implementation), and sprint state
is maintained in a `SprintContextStoreProtocol` implementation. Scheduled cron
triggers drive ceremony outputs (pre-standup brief, retro draft, release notes)
via the same event bus.

In PoC / demo mode (`SCRUMAGENT_MOCK=1`), the in-memory `MockSprintContextStore`
and `MockWatsonxClient` replace all real integrations. Output goes to stdout via
`ConsoleSink`.

## Architecture Decisions

1. **Python 3.12 + uv workspace monorepo** — single repo, separate installable
   packages per concern. All services share `scrumagent_shared` for event types
   so interface drift is impossible.
2. **Redis Streams (redis-py) for the event bus** — at-least-once delivery with
   XREADGROUP / XACK. Local dev needs no broker beyond `docker compose up redis`.
   Production targets Red Hat AMQ Streams or Redis Enterprise on OpenShift.
3. **Redis Stack (JSON + RedisVL HNSW vector)** for sprint state — one service
   covers both relational-style lookups (burndown, WIP) and vector embeddings
   (retro clustering). Replaced pgvector+Postgres to reduce PoC infra surface.
4. **Protocol-first dependency injection** — processors accept
   `WatsonxClientProtocol` and `SprintContextStoreProtocol`, never the concrete
   classes. `SCRUMAGENT_MOCK=1` swaps implementations without touching processor
   code.
5. **Red Hat UBI9 base images** — all Dockerfiles use
   `registry.redhat.io/ubi9/python-311-minimal` with non-root user UID 1001.
   Services bind to `127.0.0.1` (not `0.0.0.0`).
6. **No secrets in code** — all credentials via environment variables + `.env`
   (gitignored). `.env.example` documents every required key.
7. **Shift-left quality gates** — `make ci` = `lint + typecheck + test`.
   Runs ruff, mypy (strict), and pytest before any PR is merged.
   Tests run without any infrastructure (Redis, WatsonX, Slack).

## Task List

### Phase 1: Foundation (Scaffold — DONE ✓)

- [x] Root monorepo (`pyproject.toml`, `.gitignore`, `.env.example`, `Makefile`)
- [x] `packages/shared` — `AgentEvent` schema, GitHub & Jira adapters
- [x] `packages/watsonx_client` — `WatsonxClientProtocol`, `MockWatsonxClient`, `WatsonxClient` stub
- [x] `packages/context_store` — `SprintContextStoreProtocol`, `MockSprintContextStore`, `SprintContextStore` (Redis JSON + RedisVL)
- [x] `packages/processors` — 5 stateless processor stubs with tests
- [x] `packages/dispatcher` — `ActionDispatcher`, `ConsoleSink` (mock), `SlackSink`, `JiraSink`
- [x] `services/ingestion` — FastAPI webhook receiver (GitHub), HMAC-SHA256 verification
- [x] `services/worker` — Redis Streams consumer + `ProcessingPipeline`
- [x] `services/scheduler` — APScheduler cron trigger service
- [x] `docker-compose.yml` + override example
- [x] `fixtures/` — demo sprint + events JSON
- [x] `prompts/` — standup digest, pre-standup brief, retro draft, release notes
- [x] `scripts/run_mock.py` — standalone 4-phase demo runner, zero infra

### Checkpoint: Foundation ✓
- [x] `make lint` passes (ruff clean)
- [x] `make typecheck` passes (mypy strict, 41 source files, 0 errors)
- [x] `make test` passes (39/39 unit tests, no infra needed)
- [x] `make mock` runs the full 4-phase demo with no external dependencies

---

### Phase 2: Core Event Flow

- [ ] **Task 1**: Jira webhook ingestion router
  - `services/ingestion/ingestion/routers/jira.py`
  - Verify `X-Atlassian-Webhook-UUID` against config
  - Test: `services/ingestion/tests/test_jira_webhook.py`

- [ ] **Task 2**: Stale PR detection processor
  - `packages/processors/scrumagent_processors/stale_pr_detector.py`
  - Input: `TRIGGER_STALE_PR_SCAN` → query store for PRs open > N days
  - Emits `PR_STALE` side-effects with Slack nag message
  - Test: `packages/processors/tests/test_stale_pr.py`

- [ ] **Task 3**: Sprint board reconciliation
  - `packages/processors/scrumagent_processors/board_reconciler.py`
  - On `TICKET_UPDATED`: compare ticket sprint vs. planning snapshot
  - Fill `TicketTrackerProcessor` scope-creep TODO stub
  - Test: `packages/processors/tests/test_board_reconciler.py`

- [ ] **Task 4**: Standup digest generator
  - `packages/processors/scrumagent_processors/standup_generator.py`
  - Input: `TRIGGER_PRE_STANDUP` — query store for last 24h per member
  - Calls `WatsonxClientProtocol.generate()` with `prompts/standup_digest.txt`
  - Emits Slack side-effect with generated digest
  - Test: `packages/processors/tests/test_standup_generator.py`

### Checkpoint: Phase 2
- [ ] End-to-end test: inject `fixtures/events.json` → Redis Stream → worker processes all
- [ ] Each processor returns non-empty `ProcessorResult` for its target event type
- [ ] `make ci` passes with new tests

---

### Phase 3: AI Ceremony Features

- [ ] **Task 5**: Pre-standup brief generator
  - `packages/processors/scrumagent_processors/pre_standup_brief.py`
  - Input: `TRIGGER_PRE_STANDUP` — reads latest `SprintSnapshot` from store
  - Calls `WatsonxClientProtocol.generate()` with `prompts/pre_standup_brief.txt`
  - Posts to Slack `#scrum-bot` channel

- [ ] **Task 6**: Retro facilitation processor
  - `packages/processors/scrumagent_processors/retro_facilitator.py`
  - Input: `TRIGGER_RETRO` — survey responses from `event.payload`
  - Calls `WatsonxClientProtocol.generate()` with `prompts/retro_draft.txt`

- [ ] **Task 7**: Release notes generator
  - `packages/processors/scrumagent_processors/release_notes_generator.py`
  - Queries closed tickets + merged PRs from store
  - Calls `WatsonxClientProtocol.generate()` with `prompts/release_notes.txt`

- [ ] **Task 8**: Burndown forecasting
  - `packages/processors/scrumagent_processors/burndown_forecaster.py`
  - On `TRIGGER_PRE_STANDUP`: linear regression over `SprintSnapshot` history
  - Adds `projected_completion_date` and `on_track` to enrichments

- [ ] **Task 9**: Stalled vs. blocked classifier
  - Extend `ActivityAggregatorProcessor` with silence detection
  - Actor silent > 1 workday + no blocker → `STALLED`
  - Actor with blocker keyword in PR comment → `BLOCKED`

### Checkpoint: Phase 3
- [ ] Live `WatsonxClient` call produces standup digest output (not mocked)
- [ ] Live `WatsonxClient` call produces pre-standup brief
- [ ] Slack message posted to test channel via `SlackSink`

---

### Phase 4: Polish & Integration

- [ ] **Task 10**: Sprint Planning assist
  - `packages/processors/scrumagent_processors/sprint_planner.py`
  - Compute velocity from last N sprint snapshots; output capacity range

- [ ] **Task 11**: Linear adapter (stretch)
  - `packages/shared/scrumagent_shared/adapters/linear.py`
  - GraphQL poll → `AgentEvent` normalisation

- [ ] **Task 12**: Remove all hardcoded values
  - No test tokens, placeholder strings, or `TODO(name)` in production paths

### Checkpoint: Phase 4 / Submission
- [ ] `make ci` passes with zero errors
- [ ] End-to-end demo: fixture events → Redis Stream → worker → Slack post (no manual steps)
- [ ] All PRs merged to `main`; release tagged `v1.0.0-submission`

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WatsonX API quota / access | High | `MockWatsonxClient` behind `SCRUMAGENT_MOCK=1` lets the full demo run without credentials |
| Schema drift between packages | High | `scrumagent_shared` is the single source of truth; any change requires updating all consumers |
| Redis unavailable in dev | Medium | Worker + ingestion gracefully retry; `make up` starts Redis Stack in one command |
| RedisVL extension missing | Medium | `SprintContextStore.init_index()` creates it automatically; `MockSprintContextStore` needs no Redis |
| Slack bot approval delay | Low | `ConsoleSink` is the dispatcher fallback in all non-production environments |

## Open Questions

- **Retro survey collection**: Does the survey form live inside this service (HTTP endpoint)
  or does it come in as a Slack slash-command?
- **Vector embedding model**: Which WatsonX embedding model to use for retro clustering?
  Document the chosen model ID in `prompts/README.md` once decided.
- **Production event bus**: Redis Streams (current PoC) vs. Red Hat AMQ Streams on OpenShift?
  Decision needed before Phase 4 hardening.
