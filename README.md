# WatsonX ScrumMaster Agent PoC

This repository is a Proof of Concept for a Scrum intelligence pipeline.
The primary demo entrypoint is [`scripts/run_mock.py`](scripts/run_mock.py), which runs the real processing flow against fixture data without Redis, Slack, Jira, or WatsonX credentials.

## What the demo shows

- GitHub-style events normalised into [`AgentEvent`](packages/shared/scrumagent_shared/events.py:62)
- A real processor pipeline in [`ProcessingPipeline`](services/worker/worker/pipeline.py:21)
- Mocked WatsonX and context storage implementations for deterministic demo output
- Console-dispatched standup and alert output via [`ConsoleSink`](packages/dispatcher/scrumagent_dispatcher/sinks/console.py:45)

## Quick start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Install dependencies

```bash
make install
```

### Run the demo

```bash
make mock
```

### Run checks

```bash
make test
```

## Optional infrastructure mode

The repository still includes Redis-backed services for a fuller demo:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
make up
make run-ingestion
make run-worker
make run-scheduler
```

These services bind only to `127.0.0.1` and use environment variables from [`.env.example`](.env.example).

## Project layout

- [`scripts/run_mock.py`](scripts/run_mock.py) — single-command PoC demo runner
- [`fixtures/`](fixtures/) — sample sprint and event data used by the demo
- [`packages/processors/`](packages/processors/) — core event processors
- [`services/worker/`](services/worker/) — processing pipeline and Redis consumer
- [`services/ingestion/`](services/ingestion/) — webhook receiver for GitHub events
- [`services/scheduler/`](services/scheduler/) — scheduled trigger emitter

## Notes

- Prompt templates live in [`prompts/`](prompts/)
- The technical proposal remains in [`watsonx-scrummaster-agent-technical-proposal.html`](watsonx-scrummaster-agent-technical-proposal.html)
- Secrets are environment-driven only; do not commit a `.env` file
