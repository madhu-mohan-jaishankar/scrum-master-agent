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
from collections import Counter
from pathlib import Path

from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor
from scrumagent_processors.burndown import BurndownProcessor
from scrumagent_processors.ceremony_summary import CeremonySummaryProcessor
from scrumagent_processors.ci_monitor import CIMonitorProcessor
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_processors.release_notes import ReleaseNotesProcessor
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
_WARN = "\033[33m⚠  {}\033[0m"
_SKIP = "\033[2m   ↷ skipped: {}\033[0m"


def _build_pipeline(store: MockSprintContextStore) -> ProcessingPipeline:
    wx = MockWatsonxClient()
    processors = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
        CeremonySummaryProcessor(wx),
        BurndownProcessor(),
        ReleaseNotesProcessor(wx),
    ]
    return ProcessingPipeline(processors=processors, store=store, dispatcher=ActionDispatcher())


def _load_events(sprint_id: str) -> tuple[list[AgentEvent], int]:
    """Return (valid_events, skipped_count) for the given sprint_id."""
    path = _FIXTURES / "events.json"
    if not path.exists():
        return [], 0
    events: list[AgentEvent] = []
    skipped = 0
    for item in json.loads(path.read_text()):
        if item.get("sprint_id") != sprint_id:
            continue
        # Edge-case: skip events that are missing required fields
        if not item.get("source") or not item.get("type"):
            print(_SKIP.format(f"missing source/type — {item}"))
            skipped += 1
            continue
        try:
            events.append(AgentEvent.model_validate(item))
        except Exception as exc:
            print(_SKIP.format(f"validation error — {exc} — {item}"))
            skipped += 1
    return events, skipped


async def run_mock(sprint_id: str, delay: float) -> None:
    print(_BANNER)
    store = MockSprintContextStore(_FIXTURES)
    pipeline = _build_pipeline(store)

    skipped_total = 0
    event_type_counts: Counter[str] = Counter()

    # ── Phase 1: replay fixture webhook events ────────────────────────────────
    print(_SECTION.format("── Phase 1: Replaying fixture webhook events ──"))
    events, skipped = _load_events(sprint_id)
    skipped_total += skipped
    if not events:
        print(f"  (no fixture events found for sprint_id={sprint_id!r})\n")
    for event in events:
        event_type_counts[event.type.value] += 1
        pr = event.payload.get("pull_request", {}) or {}
        pr_num = pr.get("number", "")
        pr_label = f" PR #{pr_num}" if pr_num else ""

        # Edge-case annotation
        comment_body = event.payload.get("comment", {}).get("body", None)
        if event.type == EventType.PR_COMMENT and comment_body == "":
            suffix = "\033[2m  [edge: empty comment body — skipped by classifier]\033[0m"
        elif event.type == EventType.COMMIT_PUSHED:
            commits = event.payload.get("commits", [])
            messages = [c.get("message", "") for c in commits]
            if any(m == "" for m in messages):
                suffix = "\033[2m  [edge: empty commit message — classifier will skip]\033[0m"
            else:
                suffix = ""
        elif event.type == EventType.TICKET_UPDATED:
            fields = event.payload.get("issue", {}).get("fields", {})
            if not fields.get("story_points") and not fields.get("customfield_10016"):
                suffix = "\033[2m  [edge: no story_points field — tracked as 0 pts]\033[0m"
            else:
                suffix = ""
        else:
            suffix = ""

        print(
            f"\033[2m→ [{event.type.value}] {event.actor or 'system'}"
            f"  repo={event.repo or 'n/a'}{pr_label}\033[0m{suffix}"
        )
        await pipeline.run(event)
        if delay > 0:
            time.sleep(delay)

    if skipped:
        print(_WARN.format(f"{skipped} event(s) skipped due to validation errors (see above)"))

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
        event_type_counts[trigger.type.value] += 1
        await pipeline.run(trigger)
        time.sleep(delay)
    else:
        print(_WARN.format(f"No snapshot found for {sprint_id!r} — pre-standup brief skipped"))

    # ── Phase 3: standup digests per team member ──────────────────────────────
    print(_SECTION.format("\n── Phase 3: Standup digests per team member ──"))
    digests_path = _FIXTURES / "standup_digests.json"
    if digests_path.exists():
        from scrumagent_dispatcher.sinks.console import ConsoleSink
        sink = ConsoleSink()
        digests = json.loads(digests_path.read_text())
        sprint_digests = [d for d in digests if d.get("sprint_id") == sprint_id]
        if not sprint_digests:
            print(f"  (no standup digests found for sprint_id={sprint_id!r})")
        for digest in sprint_digests:
            # Edge-case: missing actor
            actor = digest.get("actor")
            if not actor:
                print(_SKIP.format(f"standup digest missing actor — {digest}"))
                skipped_total += 1
                continue

            ev = AgentEvent(
                source=EventSource.SLACK,
                type=EventType.STANDUP_RESPONSE,
                actor=actor,
                sprint_id=sprint_id,
                payload=digest,
            )
            event_type_counts[ev.type.value] += 1
            await pipeline.run(ev)

            wip_warning = ""
            if digest.get("wip_count", 0) == 0 and digest.get("velocity_pts_yesterday", 0) == 0:
                wip_warning = "  \033[33m[no WIP & zero velocity — new/blocked member]\033[0m"

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
            if wip_warning:
                print(wip_warning)
            time.sleep(delay)

    # ── Phase 4: retro trigger ────────────────────────────────────────────────
    print(_SECTION.format("\n── Phase 4: Retrospective trigger ──"))
    survey_path = _FIXTURES / "retro_survey.json"
    if survey_path.exists():
        sprint_survey = [
            r for r in json.loads(survey_path.read_text()) if r.get("sprint_id") == sprint_id
        ]
        if not sprint_survey:
            print(f"  (no retro survey responses found for sprint_id={sprint_id!r})")
        else:
            retro_event = AgentEvent(
                source=EventSource.INTERNAL,
                type=EventType.TRIGGER_RETRO,
                sprint_id=sprint_id,
                payload={"survey_responses": sprint_survey},
            )
            event_type_counts[retro_event.type.value] += 1
            await pipeline.run(retro_event)
            sentiments = Counter(r.get("sentiment", "unknown") for r in sprint_survey)
            print(
                f"  \033[2m{len(sprint_survey)} survey responses — "
                + ", ".join(f"{k}: {v}" for k, v in sorted(sentiments.items()))
                + "\033[0m"
            )
            time.sleep(delay)

    # ── Phase 5: stale PR scan trigger ────────────────────────────────────────
    print(_SECTION.format("\n── Phase 5: Scheduled trigger — stale PR scan ──"))
    stale_events = [e for e in events if e.type == EventType.PR_STALE]
    if stale_events:
        scan_trigger = AgentEvent(
            source=EventSource.INTERNAL,
            type=EventType.TRIGGER_STALE_PR_SCAN,
            sprint_id=sprint_id,
            payload={
                "stale_prs": [
                    {
                        "repo": e.repo,
                        "pr_number": e.payload.get("pull_request", {}).get("number"),
                        "title": e.payload.get("pull_request", {}).get("title"),
                        "days_open": e.payload.get("pull_request", {}).get("days_open"),
                        "approved": e.payload.get("pull_request", {}).get("approved"),
                        "ci_status": e.payload.get("pull_request", {}).get("ci_status"),
                    }
                    for e in stale_events
                ]
            },
        )
        event_type_counts[scan_trigger.type.value] += 1
        await pipeline.run(scan_trigger)
        time.sleep(delay)
    else:
        print("  (no stale PR events in fixture — scan skipped)")

    # ── Phase 7: ceremony summaries ──────────────────────────────────────────
    print(_SECTION.format("\n── Phase 7: Ceremony summaries ──"))
    ceremonies_path = _FIXTURES / "ceremonies.json"
    if ceremonies_path.exists():
        ceremonies = json.loads(ceremonies_path.read_text())
        # Group by sprint_id — show ceremonies for this sprint first, then others.
        sprint_ceremonies = [c for c in ceremonies if c.get("sprint_id") == sprint_id]
        other_ceremonies = [c for c in ceremonies if c.get("sprint_id") != sprint_id]
        all_ordered = sprint_ceremonies + other_ceremonies

        if not all_ordered:
            print("  (no ceremony records found)")
        else:
            _CEREMONY_LABELS = {
                "daily_standup":  "Daily Standup",
                "sprint_review":  "Sprint Review",
                "retrospective":  "Retrospective",
                "sprint_planning": "Sprint Planning",
                "all_hands":      "All-Hands",
            }
            for ceremony in all_ordered:
                ctype = ceremony.get("ceremony_type", "unknown")
                clabel = _CEREMONY_LABELS.get(ctype, ctype.replace("_", " ").title())
                cer_sprint = ceremony.get("sprint_id", "?")
                cer_date = (ceremony.get("date") or "")[:10]
                print(
                    f"\033[2m  ↳ {clabel:<20} sprint={cer_sprint}  date={cer_date}\033[0m"
                )
                ev = AgentEvent(
                    source=EventSource.INTERNAL,
                    type=EventType.TRIGGER_CEREMONY_SUMMARY,
                    sprint_id=cer_sprint,
                    payload={"ceremony": ceremony},
                )
                event_type_counts[ev.type.value] += 1
                await pipeline.run(ev)
                if delay > 0:
                    time.sleep(delay)
    else:
        print(_WARN.format("fixtures/ceremonies.json not found — ceremony summaries skipped"))

    # ── Phase 6: sprint planning trigger ─────────────────────────────────────
    print(_SECTION.format("\n── Phase 6: Sprint planning trigger ──"))
    next_sprint_id = _next_sprint_id(sprint_id)
    next_snapshot = await store.get_sprint_snapshot(next_sprint_id)
    planning_trigger = AgentEvent(
        source=EventSource.INTERNAL,
        type=EventType.TRIGGER_SPRINT_PLANNING,
        sprint_id=next_sprint_id,
        payload={
            "current_sprint_id": sprint_id,
            "next_sprint_id": next_sprint_id,
            "snapshot": next_snapshot or {},
        },
    )
    event_type_counts[planning_trigger.type.value] += 1
    await pipeline.run(planning_trigger)
    if not next_snapshot:
        print(_WARN.format(f"No snapshot for {next_sprint_id!r} — planning used empty context"))
    time.sleep(delay)

    # ── Phase 9: release notes ────────────────────────────────────────────────
    print(_SECTION.format("\n── Phase 9: Release notes ──"))
    release_items_path = _FIXTURES / "release_items.json"
    if release_items_path.exists():
        all_releases = json.loads(release_items_path.read_text())
        sprint_releases = [r for r in all_releases if r.get("sprint_id") == sprint_id]
        other_releases  = [r for r in all_releases if r.get("sprint_id") != sprint_id]
        for release_data in sprint_releases + other_releases:
            r_sprint = release_data.get("sprint_id", "?")
            version  = release_data.get("version", "")
            n_prs    = len(release_data.get("merged_prs", []))
            n_closed = len(release_data.get("closed_tickets", []))
            n_carry  = len(release_data.get("carried_over_tickets", []))
            print(
                f"\033[2m  ↳ {r_sprint:<12} {version:<8} "
                f"{n_prs} PRs · {n_closed} tickets closed"
                + (f" · {n_carry} carried over" if n_carry else "")
                + "\033[0m"
            )
            ev = AgentEvent(
                source=EventSource.INTERNAL,
                type=EventType.TRIGGER_RELEASE_NOTES,
                sprint_id=r_sprint,
                payload=release_data,
            )
            event_type_counts[ev.type.value] += 1
            await pipeline.run(ev)
            if delay > 0:
                time.sleep(delay)
    else:
        print(_WARN.format("fixtures/release_items.json not found — release notes skipped"))

    # ── Phase 8: burndown chart ───────────────────────────────────────────────
    print(_SECTION.format("\n── Phase 8: Burndown chart ──"))
    burndown_path = _FIXTURES / "burndown_data.json"
    if burndown_path.exists():
        all_burndown = json.loads(burndown_path.read_text())
        # Render chart for the current sprint, then any others in the file.
        sprint_bd = [b for b in all_burndown if b.get("sprint_id") == sprint_id]
        other_bd  = [b for b in all_burndown if b.get("sprint_id") != sprint_id]
        for bd in sprint_bd + other_bd:
            bd_sprint = bd.get("sprint_id", "?")
            bd_snapshot = await store.get_sprint_snapshot(bd_sprint)
            ev = AgentEvent(
                source=EventSource.INTERNAL,
                type=EventType.TRIGGER_BURNDOWN,
                sprint_id=bd_sprint,
                payload={
                    "burndown_data": bd,
                    "snapshot": bd_snapshot or {},
                },
            )
            event_type_counts[ev.type.value] += 1
            await pipeline.run(ev)
            if delay > 0:
                time.sleep(delay)
    else:
        print(_WARN.format("fixtures/burndown_data.json not found — burndown skipped"))

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(store.all_events())
    print("\n" + "─" * 64)
    print("\033[1m\033[32m✔ Mock run complete\033[0m")
    print(f"  Total events in store : {total}")
    print(f"  Fixture events loaded : {len(events)}  (skipped: {skipped_total})")
    print(f"  Trigger events fired  : {sum(1 for k in event_type_counts if k.startswith('trigger.'))}")
    print()
    print("  Event breakdown:")
    for etype, count in sorted(event_type_counts.items()):
        bar = "█" * count
        print(f"    {etype:<30} {bar} {count}")
    print("─" * 64 + "\n")


def _next_sprint_id(sprint_id: str) -> str:
    """Increment the numeric suffix of a sprint ID string, e.g. SPRINT-42 → SPRINT-43."""
    prefix, _, num = sprint_id.rpartition("-")
    if num.isdigit():
        return f"{prefix}-{int(num) + 1}"
    return f"{sprint_id}-NEXT"


def main() -> None:
    parser = argparse.ArgumentParser(description="ScrumAgent PoC demo runner")
    parser.add_argument("--sprint-id", default="SPRINT-42")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Seconds to pause between events (default: 0.3)")
    args = parser.parse_args()
    asyncio.run(run_mock(sprint_id=args.sprint_id, delay=args.delay))


if __name__ == "__main__":
    main()
