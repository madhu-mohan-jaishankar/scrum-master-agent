#!/usr/bin/env python
"""WatsonX ScrumMaster Agent — MCP server.

Exposes the pipeline as Bob tools over STDIO transport so Bob can invoke
the scrum intelligence pipeline conversationally.

Registered tools
----------------
run_mock_pipeline         Run the full mock pipeline (all phases) for a sprint.
run_phase                 Run a single named phase for a sprint.
get_sprint_snapshot       Return the in-memory sprint context snapshot.
sync_github_project       Sync a GitHub Projects board into the pipeline as ticket events.
get_github_project        Return raw GitHub Projects items for a sprint (fixture or live).
analyze_sprint_activity   Cross-reference GitHub Projects, events, and standup digests
                          per developer.
list_event_types          List all known EventType values.
list_processors           List the processors registered in the pipeline.
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
# GitHub Projects helpers
# ─────────────────────────────────────────────────────────────────────────────

_GH_PROJECTS_GRAPHQL = """
query($org: String!, $number: Int!, $cursor: String) {
  organization(login: $org) {
    projectV2(number: $number) {
      title
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2Field { name } }
              }
            }
          }
          content {
            ... on Issue {
              title url
              assignees(first: 10) { nodes { login } }
            }
            ... on PullRequest {
              title url
              assignees(first: 10) { nodes { login } }
            }
          }
        }
      }
    }
  }
}
"""


def _normalise_gh_project_item(node: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw GraphQL ProjectV2Item node into a flat item dict."""
    content = node.get("content") or {}
    assignees = [a["login"] for a in content.get("assignees", {}).get("nodes", [])]

    status: str = ""
    story_points: float | None = None

    for fv in node.get("fieldValues", {}).get("nodes", []):
        field_name = (fv.get("field") or {}).get("name", "").lower()
        if field_name == "status":
            status = fv.get("name", "")
        elif field_name in ("story points", "points", "estimate"):
            raw = fv.get("number")
            if raw is not None:
                story_points = float(raw)

    return {
        "id": node.get("id", ""),
        "title": content.get("title", ""),
        "status": status,
        "assignees": assignees,
        "story_points": story_points,
        "url": content.get("url"),
    }

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
async def sync_github_project(
    sprint_id: str = "SPRINT-42",
    org: str = "",
    project_number: int = 0,
) -> str:
    """Sync a GitHub Projects board into the pipeline as TICKET_SYNCED events.

    When org/project_number are omitted (or the GitHub MCP is unavailable),
    falls back to fixtures/github_projects.json so the tool always works in
    mock mode.

    Args:
        sprint_id: Sprint to associate the synced tickets with.
        org: GitHub organisation that owns the project (e.g. "my-org").
        project_number: The project board number shown in the GitHub Projects URL.
    """
    items: list[dict[str, Any]] = []
    project_title = "unknown"
    source_label = "fixture"

    fixture_path = _FIXTURES / "github_projects.json"

    if org and project_number:
        # ── Live path: call the GitHub MCP GraphQL endpoint ───────────────────
        # The GitHub MCP server exposes a graphql tool; we call it here if the
        # caller has configured it.  On any error we fall back to fixtures.
        try:
            import importlib

            gh_mcp = importlib.import_module("github_mcp_client")
            result = await gh_mcp.graphql(
                query=_GH_PROJECTS_GRAPHQL,
                variables={"org": org, "number": project_number},
            )
            project = result["data"]["organization"]["projectV2"]
            project_title = project.get("title", f"Project #{project_number}")
            nodes = project["items"]["nodes"]
            items = [_normalise_gh_project_item(n) for n in nodes if n.get("content")]
            source_label = f"live ({org}/projects/{project_number})"
        except Exception as exc:
            return (
                f"⚠  GitHub MCP call failed ({exc}). "
                "Pass org= and project_number= and ensure the GitHub MCP server "
                "is registered in .bob/mcp.json, or omit them to use fixture data."
            )
    elif fixture_path.exists():
        # ── Mock path: replay fixtures/github_projects.json ───────────────────
        all_projects: list[dict[str, Any]] = json.loads(fixture_path.read_text())
        matched = [p for p in all_projects if p.get("sprint_id") == sprint_id]
        if not matched:
            return f"(no github_projects fixture data found for sprint_id={sprint_id!r})"
        project_data = matched[0]
        project_title = project_data.get("project_title", "unknown")
        org = project_data.get("org", "demo-org")
        project_number = project_data.get("project_number", 0)
        items = project_data.get("items", [])
    else:
        return (
            "No org/project_number provided and fixtures/github_projects.json "
            "not found. Pass org= and project_number= to sync a live project."
        )

    if not items:
        return f"GitHub Projects sync: no items found for sprint_id={sprint_id!r}"

    # ── Run items through the pipeline as a TICKET_SYNCED event ──────────────
    store = MockSprintContextStore(_FIXTURES)
    pipeline = _build_pipeline(store)

    sync_event = AgentEvent(
        source=EventSource.GITHUB_PROJECTS,
        type=EventType.TICKET_SYNCED,
        sprint_id=sprint_id,
        payload={
            "project_title": project_title,
            "project_number": project_number,
            "org": org,
            "items": items,
        },
    )
    await pipeline.run(sync_event)

    # ── Build summary ─────────────────────────────────────────────────────────
    status_counts: dict[str, int] = {}
    blocked: list[str] = []
    for item in items:
        s = str(item.get("status", "unknown"))
        status_counts[s] = status_counts.get(s, 0) + 1
        if s.lower() == "blocked":
            blocked.append(item.get("title", "?"))

    lines = [
        f"✔ GitHub Projects sync complete ({source_label})",
        f"  Project : {project_title}",
        f"  Sprint  : {sprint_id}",
        f"  Items   : {len(items)}",
        "",
        "  Status breakdown:",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"    {status:<16} {count}")

    if blocked:
        lines.append("")
        lines.append(f"  ⚠  Blocked items ({len(blocked)}):")
        for title in blocked:
            lines.append(f"    • {title}")

    return "\n".join(lines)


@mcp.tool()
async def get_github_project(
    sprint_id: str = "SPRINT-42",
    org: str = "",
    project_number: int = 0,
) -> str:
    """Return GitHub Projects items for a sprint as JSON — without running the pipeline.

    Useful for inspecting raw ticket state before deciding whether to sync.
    Falls back to fixtures/github_projects.json when org/project_number are omitted.

    Args:
        sprint_id: Sprint to look up.
        org: GitHub organisation that owns the project.
        project_number: The project board number.
    """
    fixture_path = _FIXTURES / "github_projects.json"

    if org and project_number:
        try:
            import importlib

            gh_mcp = importlib.import_module("github_mcp_client")
            result = await gh_mcp.graphql(
                query=_GH_PROJECTS_GRAPHQL,
                variables={"org": org, "number": project_number},
            )
            project = result["data"]["organization"]["projectV2"]
            items = [
                _normalise_gh_project_item(n)
                for n in project["items"]["nodes"]
                if n.get("content")
            ]
            return json.dumps(
                {"project_title": project["title"], "org": org, "items": items},
                indent=2,
            )
        except Exception as exc:
            return f"⚠  GitHub MCP call failed: {exc}"

    if fixture_path.exists():
        all_projects: list[dict[str, Any]] = json.loads(fixture_path.read_text())
        matched = [p for p in all_projects if p.get("sprint_id") == sprint_id]
        if not matched:
            return f"(no fixture data found for sprint_id={sprint_id!r})"
        return json.dumps(matched[0], indent=2)

    return (
        "No data source available — pass org= and project_number= "
        "or add fixtures/github_projects.json"
    )


@mcp.tool()
async def analyze_sprint_activity(
    sprint_id: str = "SPRINT-42",
    org: str = "",
    project_number: int = 0,
) -> str:
    """Cross-reference GitHub Projects, events, and standup digests per developer.

    Produces a unified "what is each critter doing" report by correlating:
    - GitHub Projects board → assigned tickets and status
    - Event stream → commits, PRs, reviews, CI failures
    - Standup digests → self-reported blockers and WIP

    Falls back to fixture data when org/project_number are omitted.

    Args:
        sprint_id: Sprint to analyze.
        org: GitHub organisation (for live mode).
        project_number: Project board number (for live mode).
    """
    store = MockSprintContextStore(_FIXTURES)

    # ── 1. Load GitHub Projects data ──────────────────────────────────────────
    fixture_path = _FIXTURES / "github_projects.json"
    items: list[dict[str, Any]] = []

    if org and project_number:
        try:
            import importlib

            gh_mcp = importlib.import_module("github_mcp_client")
            result = await gh_mcp.graphql(
                query=_GH_PROJECTS_GRAPHQL,
                variables={"org": org, "number": project_number},
            )
            project = result["data"]["organization"]["projectV2"]
            items = [
                _normalise_gh_project_item(n)
                for n in project["items"]["nodes"]
                if n.get("content")
            ]
        except Exception:
            pass  # fall through to fixture

    if not items and fixture_path.exists():
        all_projects: list[dict[str, Any]] = json.loads(fixture_path.read_text())
        matched = [p for p in all_projects if p.get("sprint_id") == sprint_id]
        if matched:
            items = matched[0].get("items", [])

    if not items:
        return f"No GitHub Projects data for sprint_id={sprint_id!r}"

    # ── 2. Load events and standup digests ────────────────────────────────────
    events = await store.get_recent_events(sprint_id, limit=500)

    standup_path = _FIXTURES / "standup_digests.json"
    standups: list[dict[str, Any]] = []
    if standup_path.exists():
        all_standups = json.loads(standup_path.read_text())
        standups = [s for s in all_standups if s.get("sprint_id") == sprint_id]

    # ── 3. Build per-actor activity profile ───────────────────────────────────
    from collections import defaultdict

    actor_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "display_name": "",
            "assigned_tickets": [],
            "commits": 0,
            "prs_opened": 0,
            "prs_merged": 0,
            "prs_closed": 0,
            "reviews_given": 0,
            "ci_failures": 0,
            "wip_count": 0,
            "self_reported_blockers": "",
            "self_reported_digest": "",
        }
    )

    # ── GitHub Projects assignments ───────────────────────────────────────────
    for item in items:
        for assignee in item.get("assignees", []):
            actor_data[assignee]["assigned_tickets"].append(
                {
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "points": item.get("story_points"),
                    "url": item.get("url"),
                }
            )

    # ── Event stream activity ─────────────────────────────────────────────────
    for ev in events:
        actor = ev.get("actor")
        if not actor or actor == "github-actions[bot]":
            continue
        ev_type = ev.get("type", "")

        if ev_type == "commit.pushed":
            actor_data[actor]["commits"] += 1
        elif ev_type == "pr.opened":
            actor_data[actor]["prs_opened"] += 1
        elif ev_type == "pr.merged":
            actor_data[actor]["prs_merged"] += 1
        elif ev_type == "pr.closed":
            actor_data[actor]["prs_closed"] += 1
        elif ev_type == "pr.comment":
            actor_data[actor]["reviews_given"] += 1
        elif ev_type == "ci.failed":
            # Count CI failures that affect this actor's repos
            repo = ev.get("repo", "")
            # Simple heuristic: if actor has commits in this repo, count it
            if any(
                e.get("actor") == actor and e.get("repo") == repo
                for e in events
                if e.get("type") == "commit.pushed"
            ):
                actor_data[actor]["ci_failures"] += 1

    # ── Standup digests ───────────────────────────────────────────────────────
    for standup in standups:
        actor = standup.get("actor")
        if actor:
            actor_data[actor]["display_name"] = standup.get("display_name", actor)
            actor_data[actor]["wip_count"] = standup.get("wip_count", 0)
            digest = standup.get("digest", "")
            actor_data[actor]["self_reported_digest"] = digest
            # Extract blockers
            if "blocked:" in digest.lower():
                lines = [ln.strip() for ln in digest.split("•") if "blocked" in ln.lower()]
                actor_data[actor]["self_reported_blockers"] = (
                    lines[0] if lines else "mentioned blockers"
                )

    # ── 4. Generate report ────────────────────────────────────────────────────
    lines = [
        f"Sprint Activity Analysis — {sprint_id}",
        "=" * 60,
        "",
    ]

    sorted_actors = sorted(
        actor_data.items(),
        key=lambda kv: (
            len(kv[1]["assigned_tickets"]),
            kv[1]["commits"],
            kv[1]["prs_opened"],
        ),
        reverse=True,
    )

    for actor, data in sorted_actors:
        display = data["display_name"] or actor
        lines.append(f"## {display} (@{actor})")
        lines.append("")

        # Assigned tickets
        tickets = data["assigned_tickets"]
        if tickets:
            lines.append(f"  **Assigned Tickets:** {len(tickets)}")
            for t in tickets:
                pts = f"{t['points']} pts" if t["points"] else "? pts"
                lines.append(f"    • [{t['status']}] {t['title']} ({pts})")
        else:
            lines.append("  **Assigned Tickets:** none")

        # Code activity
        lines.append("")
        lines.append("  **Code Activity:**")
        lines.append(f"    Commits: {data['commits']}")
        lines.append(f"    PRs opened: {data['prs_opened']}")
        lines.append(f"    PRs merged: {data['prs_merged']}")
        lines.append(f"    PRs closed: {data['prs_closed']}")
        lines.append(f"    Reviews given: {data['reviews_given']}")
        if data["ci_failures"]:
            lines.append(f"    ⚠  CI failures: {data['ci_failures']}")

        # Standup digest
        if data["self_reported_digest"]:
            lines.append("")
            lines.append("  **Self-Reported Status:**")
            lines.append(f"    WIP count: {data['wip_count']}")
            digest_lines = [
                ln.strip() for ln in data["self_reported_digest"].split("•") if ln.strip()
            ]
            for ln in digest_lines[:3]:  # first 3 bullets
                lines.append(f"    • {ln}")
            if data["self_reported_blockers"]:
                lines.append(f"    🚨 Blocker: {data['self_reported_blockers']}")

        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_tickets = sum(len(d["assigned_tickets"]) for d in actor_data.values())
    total_commits = sum(d["commits"] for d in actor_data.values())
    total_prs = sum(d["prs_opened"] for d in actor_data.values())
    blocked_actors = [
        actor for actor, d in actor_data.items() if d["self_reported_blockers"]
    ]

    lines.append("## Summary")
    lines.append(f"  Developers: {len(actor_data)}")
    lines.append(f"  Total assigned tickets: {total_tickets}")
    lines.append(f"  Total commits: {total_commits}")
    lines.append(f"  Total PRs opened: {total_prs}")
    if blocked_actors:
        lines.append(f"  ⚠  Blocked developers: {', '.join(blocked_actors)}")

    return "\n".join(lines)


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
