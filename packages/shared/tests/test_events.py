"""Unit tests for AgentEvent and adapter normalisation."""

from scrumagent_shared.adapters.github import normalise_github_webhook
from scrumagent_shared.adapters.jira import normalise_jira_webhook
from scrumagent_shared.events import EventSource, EventType


def test_github_pr_opened_normalises() -> None:
    payload = {
        "action": "opened",
        "repository": {"full_name": "org/repo"},
        "sender": {"login": "alice"},
        "pull_request": {"number": 42, "title": "Add feature"},
    }
    event = normalise_github_webhook("pull_request", payload)
    assert event is not None
    assert event.type == EventType.PR_OPENED
    assert event.source == EventSource.GITHUB
    assert event.actor == "alice"
    assert event.repo == "org/repo"


def test_github_unknown_event_returns_none() -> None:
    event = normalise_github_webhook("ping", {"zen": "Keep it logically awesome."})
    assert event is None


def test_jira_issue_created_normalises() -> None:
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {"fields": {}},
        "user": {"displayName": "Bob"},
    }
    event = normalise_jira_webhook(payload)
    assert event is not None
    assert event.type == EventType.TICKET_CREATED
    assert event.actor == "Bob"
