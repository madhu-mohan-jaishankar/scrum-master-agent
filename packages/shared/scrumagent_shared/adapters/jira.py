"""Jira webhook → AgentEvent normaliser."""

from __future__ import annotations

from typing import Any

from scrumagent_shared.events import AgentEvent, EventSource, EventType

_JIRA_EVENT_TO_TYPE: dict[str, EventType] = {
    "jira:issue_created": EventType.TICKET_CREATED,
    "jira:issue_updated": EventType.TICKET_UPDATED,
    "jira:issue_deleted": EventType.TICKET_CLOSED,
}


def normalise_jira_webhook(payload: dict[str, Any]) -> AgentEvent | None:
    """Return an AgentEvent or None if the Jira event is not relevant.

    Args:
        payload: parsed JSON body from Jira.

    Returns:
        An AgentEvent, or None when the incoming event should be discarded.
    """
    jira_event: str = payload.get("webhookEvent", "")
    event_type = _JIRA_EVENT_TO_TYPE.get(jira_event)
    if event_type is None:
        return None

    issue = payload.get("issue", {})
    fields = issue.get("fields", {})
    actor_obj = payload.get("user") or fields.get("assignee") or {}
    actor: str | None = actor_obj.get("displayName") or actor_obj.get("name")
    sprint_id: str | None = None

    return AgentEvent(
        source=EventSource.JIRA,
        type=event_type,
        actor=actor,
        sprint_id=sprint_id,
        payload=payload,
    )
