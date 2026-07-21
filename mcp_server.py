#!/usr/bin/env python
"""WatsonX ScrumMaster Agent — MCP server.

Exposes the pipeline as Bob tools over STDIO transport so Bob can invoke
the scrum intelligence pipeline conversationally.

Registered tools
----------------
run_mock_pipeline   Run the full mock pipeline (all phases) for a sprint.
run_phase           Run a single named phase for a sprint.
get_sprint_snapshot Return the in-memory sprint context snapshot.
list_event_types    List all known EventType values.
list_processors     List the processors registered in the pipeline.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# ── MCP SDK ──────────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP

# ── Project packages ─────────────────────────────────────────────────────────
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

# ── Logging — always stderr so it never touches the STDIO protocol channel ──
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

_FIXTURES = Path(__file__).parent / "fixtures"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_pipeline(store: MockSprintContextStore) -> ProcessingPipeline:
    wx = MockWatsonxClient()
    processors: list[Any] = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
        CeremonySummaryProcessor(wx),
        BurndownProcessor(),
        ReleaseNotesProcessor(wx),
    ]
    return ProcessingPipeline(
        processors=processors,
        store=store,
        dispatcher=ActionDispatcher(),
    )


def _load_events(sprint_id: str) -> tuple[list[AgentEvent], int]:
    path = _FIXTURES / "events.json"
    if not path.exists():
        return [], 0
    events: list[AgentEvent] = []
    skipped = 0
    for item in json.loads(path.read_text()):
        if item.get("sprint_id") != sprint_id:
            continue
        if not item.get("source") or not item.get("type"):
            skipped += 1
            continue
        try:
            events.append(AgentEvent.model_validate(item))
        except Exception:
            skipped += 1
    return events, skipped


def _next_sprint_id(sprint_id: str) -> str:
    prefix, _, num = sprint_id.rpartition("-")
    if num.isdigit():
        return f"{prefix}-{int(num) + 1}"
    return f"{sprint_id}-NEXT"


# ─────────────────────────────────────────────────────────────────────────────
# Phase runners — each returns a list of plain-text output lines
# ─────────────────────────────────────────────────────────────────────────────


async def _phase_events(
    pipeline: ProcessingPipeline, sprint_id: str
) -> tuple[list[str], list[AgentEvent], int]:
    """Phase 1: replay fixture webhook events. Returns (lines, events, skipped)."""
    events, skipped = _load_events(sprint_id)
    lines: list[str] = []
    if not events:
        lines.append(f"(no fixture events found for sprint_id={sprint_id!r})")
        return lines, events, skipped
    for event in events:
        pr = event.payload.get("pull_request", {}) or {}
        pr_label = f" PR #{pr['number']}" if pr.get("number") else ""
        lines.append(
            f"→ [{event.type.value}] {event.actor or 'system'}"
            f"  repo={event.repo or 'n/a'}{pr_label}"
        )
        await pipeline.run(event)
    if skipped:
        lines.append(f"⚠  {skipped} event(s) skipped due to validation errors")
    return lines, events, skipped


async def _phase_pre_standup(
    pipeline: ProcessingPipeline, store: MockSprintContextStore, sprint_id: str
) -> list[str]:
    """Phase 2: pre-standup brief trigger."""
    snapshot = await store.get_sprint_snapshot(sprint_id)
    if not snapshot:
        return [f"⚠  No snapshot found for {sprint_id!r} — pre-standup brief skipped"]
    trigger = AgentEvent(
        source=EventSource.INTERNAL,
        type=EventType.TRIGGER_PRE_STANDUP,
        sprint_id=sprint_id,
        payload={"snapshot": snapshot},
    )
    await pipeline.run(trigger)
    return [f"Pre-standup brief triggered for {sprint_id}"]


async def _phase_standup_digests(
    pipeline: ProcessingPipeline, sprint_id: str
) -> list[str]:
    """Phase 3: standup digests per team member."""
    path = _FIXTURES / "standup_digests.json"
    if not path.exists():
        return ["(standup_digests.json not found — phase skipped)"]
    lines: list[str] = []
    digests = [d for d in json.loads(path.read_text()) if d.get("sprint_id") == sprint_id]
    if not digests:
        return [f"(no standup digests found for sprint_id={sprint_id!r})"]
    for digest in digests:
        actor = digest.get("actor")
        if not actor:
            lines.append("↷ skipped: standup digest missing actor")
            continue
        ev = AgentEvent(
            source=EventSource.SLACK,
            type=EventType.STANDUP_RESPONSE,
            actor=actor,
            sprint_id=sprint_id,
            payload=digest,
        )
        await pipeline.run(ev)
        lines.append(
            f"✔ standup digest dispatched for {digest.get('display_name', actor)}"
            f" (WIP: {digest.get('wip_count', 0)})"
        )
    return lines


async def _phase_retro(pipeline: ProcessingPipeline, sprint_id: str) -> list[str]:
    """Phase 4: retrospective trigger."""
    path = _FIXTURES / "retro_survey.json"
    if not path.exists():
        return ["(retro_survey.json not found — phase skipped)"]
    responses = [r for r in json.loads(path.read_text()) if r.get("sprint_id") == sprint_id]
    if not responses:
        return [f"(no retro survey responses found for sprint_id={sprint_id!r})"]
    ev = AgentEvent(
        source=EventSource.INTERNAL,
        type=EventType.TRIGGER_RETRO,
        sprint_id=sprint_id,
        payload={"survey_responses": responses},
    )
    await pipeline.run(ev)
    return [f"Retro triggered with {len(responses)} survey responses"]


async def _phase_stale_prs(
    pipeline: ProcessingPipeline, sprint_id: str, events: list[AgentEvent]
) -> list[str]:
    """Phase 5: stale PR scan trigger."""
    stale = [e for e in events if e.type == EventType.PR_STALE]
    if not stale:
        return ["(no stale PR events in fixture — scan skipped)"]
    ev = AgentEvent(
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
                }
                for e in stale
            ]
        },
    )
    await pipeline.run(ev)
    return [f"Stale PR scan triggered for {len(stale)} PR(s)"]


async def _phase_sprint_planning(
    pipeline: ProcessingPipeline, store: MockSprintContextStore, sprint_id: str
) -> list[str]:
    """Phase 6: sprint planning trigger."""
    next_id = _next_sprint_id(sprint_id)
    snapshot = await store.get_sprint_snapshot(next_id)
    ev = AgentEvent(
        source=EventSource.INTERNAL,
        type=EventType.TRIGGER_SPRINT_PLANNING,
        sprint_id=next_id,
        payload={
            "current_sprint_id": sprint_id,
            "next_sprint_id": next_id,
            "snapshot": snapshot or {},
        },
    )
    await pipeline.run(ev)
    note = "" if snapshot else f" ⚠  no snapshot for {next_id!r} — empty context used"
    return [f"Sprint planning triggered for {next_id}{note}"]


# ─────────────────────────────────────────────────────────────────────────────
# MCP server
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("scrumagent")


@mcp.tool()
async def run_mock_pipeline(sprint_id: str = "SPRINT-42") -> str:
    """Run the full ScrumMaster Agent mock pipeline (all phases) for a sprint.

    No Redis, WatsonX API key, or Slack token required — everything runs
    in-memory using mock implementations.

    Args:
        sprint_id: Jira-style sprint identifier, e.g. "SPRINT-42".
    """
    store = MockSprintContextStore(_FIXTURES)
    pipeline = _build_pipeline(store)
    output: list[str] = []

    output.append(f"=== WatsonX ScrumMaster Agent — Mock Pipeline ({sprint_id}) ===\n")

    output.append("── Phase 1: Fixture webhook events ──")
    lines, events, _ = await _phase_events(pipeline, sprint_id)
    output.extend(lines)

    output.append("\n── Phase 2: Pre-standup brief ──")
    output.extend(await _phase_pre_standup(pipeline, store, sprint_id))

    output.append("\n── Phase 3: Standup digests ──")
    output.extend(await _phase_standup_digests(pipeline, sprint_id))

    output.append("\n── Phase 4: Retrospective ──")
    output.extend(await _phase_retro(pipeline, sprint_id))

    output.append("\n── Phase 5: Stale PR scan ──")
    output.extend(await _phase_stale_prs(pipeline, sprint_id, events))

    output.append("\n── Phase 6: Sprint planning ──")
    output.extend(await _phase_sprint_planning(pipeline, store, sprint_id))

    total = len(store.all_events())
    output.append(f"\n✔ Done — {total} event(s) stored in sprint context")
    return "\n".join(output)


@mcp.tool()
async def run_phase(phase: str, sprint_id: str = "SPRINT-42") -> str:
    """Run a single pipeline phase for a sprint.

    Args:
        phase: One of "events", "pre_standup", "standup", "retro",
               "stale_prs", "sprint_planning".
        sprint_id: Jira-style sprint identifier, e.g. "SPRINT-42".
    """
    valid = {"events", "pre_standup", "standup", "retro", "stale_prs", "sprint_planning"}
    if phase not in valid:
        return f"Unknown phase {phase!r}. Valid phases: {', '.join(sorted(valid))}"

    store = MockSprintContextStore(_FIXTURES)
    pipeline = _build_pipeline(store)

    if phase == "events":
        lines, _, _ = await _phase_events(pipeline, sprint_id)
    elif phase == "pre_standup":
        lines = await _phase_pre_standup(pipeline, store, sprint_id)
    elif phase == "standup":
        lines = await _phase_standup_digests(pipeline, sprint_id)
    elif phase == "retro":
        lines = await _phase_retro(pipeline, sprint_id)
    elif phase == "stale_prs":
        events_loaded, _ = _load_events(sprint_id)
        lines = await _phase_stale_prs(pipeline, sprint_id, events_loaded)
    else:  # sprint_planning
        lines = await _phase_sprint_planning(pipeline, store, sprint_id)

    return "\n".join(lines)


@mcp.tool()
async def get_sprint_snapshot(sprint_id: str = "SPRINT-42") -> str:
    """Return the in-memory sprint context snapshot as JSON.

    Args:
        sprint_id: Jira-style sprint identifier, e.g. "SPRINT-42".
    """
    store = MockSprintContextStore(_FIXTURES)
    snapshot = await store.get_sprint_snapshot(sprint_id)
    if snapshot is None:
        return f"No snapshot found for sprint_id={sprint_id!r}"
    return json.dumps(snapshot, indent=2, default=str)


@mcp.tool()
def list_event_types() -> str:
    """List all EventType values supported by the pipeline."""
    lines = [f"  {e.value}" for e in EventType]
    return "Event types:\n" + "\n".join(lines)


@mcp.tool()
def list_processors() -> str:
    """List the processors registered in the mock pipeline."""
    names = [
        "PRClassifierProcessor",
        "CommitAnalyserProcessor",
        "CIMonitorProcessor",
        "TicketTrackerProcessor",
        "ActivityAggregatorProcessor",
        "CeremonySummaryProcessor",
        "BurndownProcessor",
        "ReleaseNotesProcessor",
    ]
    return "Processors (in execution order):\n" + "\n".join(f"  {n}" for n in names)


if __name__ == "__main__":
    mcp.run(transport="stdio")
