"""Ticket Tracker Processor.

Tracks ticket lifecycle events and detects mid-sprint scope creep.
Scope creep is defined as: total story points added after sprint day 1
exceeding SCOPE_CREEP_THRESHOLD_PCT of the original sprint commitment.

The planning snapshot (total points at sprint start) must be stored in
the Sprint Context Store and retrieved here for comparison.

Also handles TICKET_SYNCED events produced by the GitHub Projects sync
tool, normalising each project item into the same enrichment shape used
by Jira/Linear ticket events.
"""

from __future__ import annotations

from typing import Any

from scrumagent_shared.events import AgentEvent, EventType

from scrumagent_processors.base import BaseProcessor, ProcessorResult

SCOPE_CREEP_THRESHOLD_PCT = 0.10  # 10 %

# GitHub Projects status values that map to our canonical statuses.
_GH_STATUS_MAP: dict[str, str] = {
    "todo": "todo",
    "in progress": "in_progress",
    "in review": "in_review",
    "done": "done",
    "closed": "done",
    "backlog": "backlog",
    "blocked": "blocked",
}


class TicketTrackerProcessor(BaseProcessor):
    """Processes Jira / Linear / GitHub Projects ticket events."""

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type == EventType.TICKET_SYNCED:
            return self._process_gh_projects_sync(event)

        if event.type not in (
            EventType.TICKET_CREATED,
            EventType.TICKET_UPDATED,
            EventType.TICKET_CLOSED,
        ):
            return ProcessorResult()

        issue = event.payload.get("issue", {})
        fields = issue.get("fields", {})
        story_points: float = float(
            fields.get("story_points") or fields.get("customfield_10016") or 0
        )
        status: str = str(fields.get("status", {}).get("name", "")).lower()

        enrichments: dict[str, Any] = {
            "ticket_story_points": story_points,
            "ticket_status": status,
        }

        return ProcessorResult(enrichments=enrichments)

    # ── GitHub Projects ────────────────────────────────────────────────────────

    def _process_gh_projects_sync(self, event: AgentEvent) -> ProcessorResult:
        """Normalise a bulk GitHub Projects sync payload into enrichments.

        Expected payload shape (produced by mcp_server.sync_github_project):
          {
            "project_title": str,
            "project_number": int,
            "org": str,
            "items": [
              {
                "id": str,
                "title": str,
                "status": str,        # raw GitHub Projects status label
                "assignees": [str],
                "story_points": float | None,
                "url": str | None,
              },
              ...
            ]
          }
        """
        items: list[dict[str, Any]] = event.payload.get("items", [])
        if not items:
            return ProcessorResult()

        status_counts: dict[str, int] = {}
        total_points: float = 0.0
        done_points: float = 0.0
        in_progress_count: int = 0
        blocked_count: int = 0

        for item in items:
            raw_status = str(item.get("status", "")).lower()
            canonical = _GH_STATUS_MAP.get(raw_status, raw_status)
            status_counts[canonical] = status_counts.get(canonical, 0) + 1

            pts = float(item.get("story_points") or 0)
            total_points += pts
            if canonical == "done":
                done_points += pts
            if canonical == "in_progress":
                in_progress_count += 1
            if canonical == "blocked":
                blocked_count += 1

        side_effects: list[dict[str, Any]] = []
        if blocked_count:
            side_effects.append(
                {
                    "type": "alert",
                    "severity": "warning",
                    "message": (
                        f"GitHub Projects sync: {blocked_count} blocked item(s) "
                        f"in '{event.payload.get('project_title', 'unknown project')}'"
                    ),
                }
            )

        enrichments: dict[str, Any] = {
            "gh_projects_status_counts": status_counts,
            "gh_projects_total_points": total_points,
            "gh_projects_done_points": done_points,
            "gh_projects_in_progress_count": in_progress_count,
            "gh_projects_blocked_count": blocked_count,
            "gh_projects_item_count": len(items),
        }

        return ProcessorResult(enrichments=enrichments, side_effects=side_effects)
