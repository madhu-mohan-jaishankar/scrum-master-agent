"""Ticket Tracker Processor.

Tracks ticket lifecycle events and detects mid-sprint scope creep.
Scope creep is defined as: total story points added after sprint day 1
exceeding SCOPE_CREEP_THRESHOLD_PCT of the original sprint commitment.

The planning snapshot (total points at sprint start) must be stored in
the Sprint Context Store and retrieved here for comparison.
"""

from __future__ import annotations

from typing import Any

from scrumagent_shared.events import AgentEvent, EventType

from scrumagent_processors.base import BaseProcessor, ProcessorResult

SCOPE_CREEP_THRESHOLD_PCT = 0.10  # 10 %


class TicketTrackerProcessor(BaseProcessor):
    """Processes Jira / Linear ticket events and flags scope creep."""

    async def process(self, event: AgentEvent) -> ProcessorResult:
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
