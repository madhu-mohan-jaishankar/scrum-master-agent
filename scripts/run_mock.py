#!/usr/bin/env python
"""Mock mode runner — runs the full ScrumAgent pipeline without any infra.

Usage:
    uv run python scripts/run_mock.py [--sprint-id SPRINT-42] [--delay 0.3]

All fixture events are fed through the real ProcessingPipeline with:
  - MockWatsonxClient   (deterministic AI responses, no API key)
  - MockSprintContextStore  (in-memory, pre-seeded from fixtures/)
  - ActionDispatcher(mock=True)  (all output pretty-printed to console)

Perfect for demos, onboarding, and CI smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure all workspace packages are importable when running from repo root.
_REPO = Path(__file__).parent.parent
for _pkg in [
    "packages/shared",
    "packages/watsonx_client",
    "packages/context_store",
    "packages/processors",
    "packages/dispatcher",
    "services/worker",
]:
    sys.path.insert(0, str(_REPO / _pkg))

# Force mock mode before any imports that read settings.
os.environ.setdefault("SCRUMAGENT_MOCK", "1")

from scrumagent_context_store.mock_store import MockSprintContextStore  # noqa: E402
from scrumagent_dispatcher.dispatcher import ActionDispatcher  # noqa: E402
from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor  # noqa: E402
from scrumagent_processors.ci_monitor import CIMonitorProcessor  # noqa: E402
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor  # noqa: E402
from scrumagent_processors.pr_classifier import PRClassifierProcessor  # noqa: E402
from scrumagent_processors.ticket_tracker import TicketTrackerProcessor  # noqa: E402
from scrumagent_shared.events import AgentEvent, EventSource, EventType  # noqa: E402
from scrumagent_watsonx.mock_client import MockWatsonxClient  # noqa: E402
from worker.pipeline import ProcessingPipeline  # noqa: E402

logging.basicConfig(level=logging.WARNING)  # suppress noisy library logs in demo
logger = logging.getLogger("mock_runner")

_FIXTURES = _REPO / "fixtures"

_BANNER = """\
\033[1m\033[36m
╔══════════════════════════════════════════════════════════════╗
║          WatsonX ScrumMaster Agent — MOCK MODE               ║
║  No Kafka · No Postgres · No API keys · Zero infra needed    ║
╚══════════════════════════════════════════════════════════════╝
\033[0m"""

_SECTION = "\033[1m\033[33m{}\033[0m"


def _build_pipeline(store: MockSprintContextStore) -> ProcessingPipeline:
    wx = MockWatsonxClient()
    dispatcher = ActionDispatcher(mock=True)
    processors = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
    ]
    return ProcessingPipeline(processors=processors, store=store, dispatcher=dispatcher)


def _load_events(sprint_id: str) -> list[AgentEvent]:
    """Load and parse fixture events, filtering by sprint_id."""
    path = _FIXTURES / "events.json"
    if not path.exists():
        logger.warning("fixtures/events.json not found — using empty event list")
        return []
    raw: list[dict] = json.loads(path.read_text())
    events = []
    for item in raw:
        if item.get("sprint_id") != sprint_id:
            continue
        try:
            events.append(AgentEvent.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping malformed fixture event: %s", exc)
    return events


def _emit_trigger(event_type: EventType, sprint_id: str) -> AgentEvent:
    return AgentEvent(
        source=EventSource.INTERNAL,
        type=event_type,
        sprint_id=sprint_id,
    )


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

    # ── Phase 2: scheduled trigger — pre-standup brief ────────────────────────
    print(_SECTION.format("\n── Phase 2: Scheduled trigger — pre-standup brief ──"))
    snapshot = await store.get_sprint_snapshot(sprint_id)
    if snapshot:
        trigger = _emit_trigger(EventType.TRIGGER_PRE_STANDUP, sprint_id)
        # Inject snapshot data into the trigger payload so the (future)
        # pre-standup processor can find it.
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
        digests: list[dict] = json.loads(digests_path.read_text())
        for digest in digests:
            if digest.get("sprint_id") != sprint_id:
                continue
            # Emit a synthetic standup response event so the pipeline sees it.
            ev = AgentEvent(
                source=EventSource.SLACK,
                type=EventType.STANDUP_RESPONSE,
                actor=digest["actor"],
                sprint_id=sprint_id,
                payload=digest,
            )
            await pipeline.run(ev)
            # Also print the pre-built digest directly (demo shortcut).
            from scrumagent_dispatcher.sinks.console import ConsoleSink

            sink = ConsoleSink()
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
        survey: list[dict] = json.loads(survey_path.read_text())
        sprint_survey = [r for r in survey if r.get("sprint_id") == sprint_id]
        retro_trigger = AgentEvent(
            source=EventSource.INTERNAL,
            type=EventType.TRIGGER_RETRO,
            sprint_id=sprint_id,
            payload={"survey_responses": sprint_survey},
        )
        await pipeline.run(retro_trigger)
        time.sleep(delay)

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(store.all_events())
    print(
        f"\n\033[1m\033[32m✔ Mock run complete — {total} events processed"
        f" ({len(events)} from fixtures + triggers)\033[0m\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ScrumAgent mock mode runner")
    parser.add_argument(
        "--sprint-id", default="SPRINT-42", help="Sprint ID to filter fixture events"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Seconds to pause between events (default: 0.3)",
    )
    args = parser.parse_args()
    asyncio.run(run_mock(sprint_id=args.sprint_id, delay=args.delay))


if __name__ == "__main__":
    main()
