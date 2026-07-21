#!/usr/bin/env python
"""PoC demo runner — runs the full ScrumAgent pipeline without any infrastructure.

Usage:
    make mock                                    # recommended
    uv run python scripts/run_mock.py [--sprint-id SPRINT-42] [--delay 0.3]

All fixture events are fed through the real ProcessingPipeline with:
  - MockWatsonxClient          — deterministic AI responses, no API key needed
  - MockSprintContextStore     — in-memory store pre-seeded from fixtures/
  - ActionDispatcher(mock=True) — all output pretty-printed to the console
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor
from scrumagent_processors.ci_monitor import CIMonitorProcessor
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_processors.ticket_tracker import TicketTrackerProcessor
from scrumagent_shared.events import AgentEvent, EventSource, EventType
from scrumagent_watsonx.mock_client import MockWatsonxClient
from worker.pipeline import ProcessingPipeline

logging.basicConfig(level=logging.WARNING)

_FIXTURES = Path(__file__).parent.parent / "fixtures"

_BANNER = """\
\033[1m\033[36m
╔══════════════════════════════════════════════════════════════╗
║          WatsonX ScrumMaster Agent — MOCK MODE               ║
║  No Redis · No WatsonX · No Slack · Zero infra needed        ║
╚══════════════════════════════════════════════════════════════╝
\033[0m"""

_SECTION = "\033[1m\033[33m{}\033[0m"


def _build_pipeline(store: MockSprintContextStore) -> ProcessingPipeline:
    wx = MockWatsonxClient()
    processors = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
    ]
    return ProcessingPipeline(processors=processors, store=store, dispatcher=ActionDispatcher())


def _load_events(sprint_id: str) -> list[AgentEvent]:
    path = _FIXTURES / "events.json"
    if not path.exists():
        return []
    events = []
    for item in json.loads(path.read_text()):
        if item.get("sprint_id") != sprint_id:
            continue
        try:
            events.append(AgentEvent.model_validate(item))
        except Exception:
            pass
    return events


async def run_mock(sprint_id: str, delay: float) -> None:
    print(_BANNER)
    store = MockSprintContextStore(_FIXTURES)
    pipeline = _build_pipeline(store)

    # ── Phase 1: replay fixture webhook events ────────────────────────────────
    print(_SECTION.format("── Phase 1: Replaying fixture webhook events ──"))
    events = _load_events(sprint_id)
    if not events:
        print(f"  (no fixture events found for sprint_id={sprint_id!r})\n")
    for event in events:
        print(
            f"\033[2m→ [{event.type.value}] {event.actor or 'system'}"
            f"  repo={event.repo or 'n/a'}\033[0m"
        )
        await pipeline.run(event)
        if delay > 0:
            time.sleep(delay)

    # ── Phase 2: pre-standup brief trigger ────────────────────────────────────
    print(_SECTION.format("\n── Phase 2: Scheduled trigger — pre-standup brief ──"))
    snapshot = await store.get_sprint_snapshot(sprint_id)
    if snapshot:
        trigger = AgentEvent(
            source=EventSource.INTERNAL,
            type=EventType.TRIGGER_PRE_STANDUP,
            sprint_id=sprint_id,
            payload={"snapshot": snapshot},
        )
        await pipeline.run(trigger)
        time.sleep(delay)

    # ── Phase 3: standup digests per team member ──────────────────────────────
    print(_SECTION.format("\n── Phase 3: Standup digests per team member ──"))
    digests_path = _FIXTURES / "standup_digests.json"
    if digests_path.exists():
        from scrumagent_dispatcher.sinks.console import ConsoleSink
        sink = ConsoleSink()
        for digest in json.loads(digests_path.read_text()):
            if digest.get("sprint_id") != sprint_id:
                continue
            ev = AgentEvent(
                source=EventSource.SLACK,
                type=EventType.STANDUP_RESPONSE,
                actor=digest["actor"],
                sprint_id=sprint_id,
                payload=digest,
            )
            await pipeline.run(ev)
            await sink.send(
                {
                    "action": "standup_digest",
                    "channel": "slack",
                    "message": (
                        f"*{digest['display_name']}* (WIP: {digest['wip_count']})\n"
                        f"{digest['digest']}"
                    ),
                }
            )
            time.sleep(delay)

    # ── Phase 4: retro trigger ────────────────────────────────────────────────
    print(_SECTION.format("\n── Phase 4: Retrospective trigger ──"))
    survey_path = _FIXTURES / "retro_survey.json"
    if survey_path.exists():
        sprint_survey = [
            r for r in json.loads(survey_path.read_text()) if r.get("sprint_id") == sprint_id
        ]
        await pipeline.run(AgentEvent(
            source=EventSource.INTERNAL,
            type=EventType.TRIGGER_RETRO,
            sprint_id=sprint_id,
            payload={"survey_responses": sprint_survey},
        ))
        time.sleep(delay)

    total = len(store.all_events())
    print(
        f"\n\033[1m\033[32m✔ Mock run complete — {total} events processed"
        f" ({len(events)} from fixtures + triggers)\033[0m\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ScrumAgent PoC demo runner")
    parser.add_argument("--sprint-id", default="SPRINT-42")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Seconds to pause between events (default: 0.3)")
    args = parser.parse_args()
    asyncio.run(run_mock(sprint_id=args.sprint_id, delay=args.delay))


if __name__ == "__main__":
    main()
