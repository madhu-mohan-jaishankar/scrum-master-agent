"""GitHub webhook → AgentEvent normaliser.

Receives the raw GitHub webhook payload dict (already signature-verified by
the ingestion service) and maps it to a canonical AgentEvent.

New event types are added here only — no other package needs to know about
GitHub-specific field names.
"""

from __future__ import annotations

from typing import Any

from scrumagent_shared.events import AgentEvent, EventSource, EventType

_ACTION_TO_EVENT_TYPE: dict[tuple[str, str], EventType] = {
    ("pull_request", "opened"): EventType.PR_OPENED,
    ("pull_request", "synchronize"): EventType.PR_UPDATED,
    ("pull_request", "closed"): EventType.PR_MERGED,   # refined by payload.merged
    ("pull_request_review", "submitted"): EventType.PR_REVIEWED,
    ("pull_request_review_comment", "created"): EventType.PR_COMMENT,
    ("push", ""): EventType.COMMIT_PUSHED,
    ("workflow_run", "completed"): EventType.CI_PASSED,  # refined below
}


def normalise_github_webhook(event_name: str, payload: dict[str, Any]) -> AgentEvent | None:
    """Return an AgentEvent or None if the event is not relevant.

    Args:
        event_name: value of the ``X-GitHub-Event`` header.
        payload: parsed JSON body from GitHub.

    Returns:
        An AgentEvent, or None when the incoming event should be discarded.
    """
    action: str = payload.get("action", "")
    key = (event_name, action) if action else (event_name, "")
    event_type = _ACTION_TO_EVENT_TYPE.get(key)
    if event_type is None:
        return None

    # Refine CI outcome
    if event_name == "workflow_run":
        conclusion = payload.get("workflow_run", {}).get("conclusion")
        if conclusion == "failure":
            event_type = EventType.CI_FAILED
        elif conclusion == "success":
            event_type = EventType.CI_PASSED

    repo_slug: str | None = payload.get("repository", {}).get("full_name")
    actor: str | None = (
        payload.get("sender", {}).get("login")
        or payload.get("pusher", {}).get("name")
    )

    return AgentEvent(
        source=EventSource.GITHUB,
        type=event_type,
        actor=actor,
        repo=repo_slug,
        payload=payload,
    )
