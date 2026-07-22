"""Canonical AgentEvent schema.

Every integration (GitHub, Jira, Slack, CI) normalises its webhook payload
into an AgentEvent before publishing to the event bus.  Nothing downstream
should ever import vendor-specific types — only AgentEvent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventSource(StrEnum):
    GITHUB = "github"
    GITHUB_PROJECTS = "github_projects"
    GITLAB = "gitlab"
    JIRA = "jira"
    LINEAR = "linear"
    SLACK = "slack"
    CI = "ci"
    INTERNAL = "internal"


class EventType(StrEnum):
    # Pull-request lifecycle
    PR_OPENED = "pr.opened"
    PR_UPDATED = "pr.updated"
    PR_REVIEWED = "pr.reviewed"
    PR_MERGED = "pr.merged"
    PR_CLOSED = "pr.closed"
    PR_COMMENT = "pr.comment"
    PR_STALE = "pr.stale"

    # Code push
    COMMIT_PUSHED = "commit.pushed"

    # CI / CD
    CI_STARTED = "ci.started"
    CI_PASSED = "ci.passed"
    CI_FAILED = "ci.failed"
    CI_FLAKY = "ci.flaky"

    # Project-management tickets
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_CLOSED = "ticket.closed"
    TICKET_SYNCED = "ticket.synced"     # bulk sync from GitHub Projects

    # Slack async standup
    STANDUP_RESPONSE = "standup.response"

    # Scheduler triggers (internal)
    TRIGGER_PRE_STANDUP = "trigger.pre_standup"
    TRIGGER_RETRO = "trigger.retro"
    TRIGGER_STALE_PR_SCAN = "trigger.stale_pr_scan"
    TRIGGER_SPRINT_PLANNING = "trigger.sprint_planning"
    TRIGGER_CEREMONY_SUMMARY = "trigger.ceremony_summary"
    TRIGGER_BURNDOWN = "trigger.burndown"
    TRIGGER_RELEASE_NOTES = "trigger.release_notes"


class AgentEvent(BaseModel):
    """Single normalised event envelope consumed by all processors."""

    id: UUID = Field(default_factory=uuid4)
    source: EventSource
    type: EventType
    actor: str | None = None          # username / bot name / system
    repo: str | None = None           # "org/repo" slug or None for non-repo events
    sprint_id: str | None = None      # Jira sprint ID or similar
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
