"""Smoke test for the mock mode runner script.

Runs the full pipeline end-to-end with mock deps — no infra, no API keys.
This is the most important test: it validates the complete signal-to-output
path works without any external dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor
from scrumagent_processors.ci_monitor import CIMonitorProcessor
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_processors.ticket_tracker import TicketTrackerProcessor
from scrumagent_shared.events import AgentEvent, EventSource, EventType
from scrumagent_watsonx.mock_client import MockWatsonxClient
from worker.pipeline import ProcessingPipeline

_FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures"


def _build_mock_pipeline() -> tuple[ProcessingPipeline, MockSprintContextStore]:
    store = MockSprintContextStore(_FIXTURES)
    wx = MockWatsonxClient()
    dispatcher = ActionDispatcher(mock=True)
    processors = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
    ]
    pipeline = ProcessingPipeline(processors=processors, store=store, dispatcher=dispatcher)
    return pipeline, store


@pytest.mark.asyncio
async def test_mock_pipeline_pr_comment_blocking(capsys: pytest.CaptureFixture[str]) -> None:
    """Blocking PR comment → alert side-effect → console output."""
    pipeline, store = _build_mock_pipeline()
    event = AgentEvent(
        source=EventSource.GITHUB,
        type=EventType.PR_COMMENT,
        actor="bob",
        repo="demo-org/frontend-web",
        sprint_id="SPRINT-42",
        payload={
            "comment": {"body": "This will break the iOS layout — must fix before merge."},
            "pull_request": {"number": 101},
        },
    )
    await pipeline.run(event)
    out = capsys.readouterr().out
    assert "ALERT" in out or "blocking" in out.lower()


@pytest.mark.asyncio
async def test_mock_pipeline_ci_failed(capsys: pytest.CaptureFixture[str]) -> None:
    """CI failure → alert dispatched to console."""
    pipeline, store = _build_mock_pipeline()
    event = AgentEvent(
        source=EventSource.CI,
        type=EventType.CI_FAILED,
        repo="demo-org/api-service",
        sprint_id="SPRINT-42",
        payload={"workflow_run": {"name": "unit-tests", "conclusion": "failure"}},
    )
    await pipeline.run(event)
    out = capsys.readouterr().out
    assert "CI failed" in out or "ALERT" in out


@pytest.mark.asyncio
async def test_mock_pipeline_persists_events_in_memory(capsys: pytest.CaptureFixture[str]) -> None:
    """Events must be persisted to the in-memory store after processing."""
    pipeline, store = _build_mock_pipeline()
    initial = len(store.all_events())

    for event_type in [EventType.PR_OPENED, EventType.COMMIT_PUSHED, EventType.TICKET_CREATED]:
        await pipeline.run(
            AgentEvent(
                source=EventSource.GITHUB,
                type=event_type,
                sprint_id="SPRINT-42",
            )
        )

    assert len(store.all_events()) == initial + 3


@pytest.mark.asyncio
async def test_mock_pipeline_replays_all_fixtures(capsys: pytest.CaptureFixture[str]) -> None:
    """Full fixture replay must complete without exceptions."""
    pipeline, store = _build_mock_pipeline()
    events_raw: list[dict[str, object]] = json.loads((_FIXTURES / "events.json").read_text())
    events = [AgentEvent.model_validate(e) for e in events_raw]

    for event in events:
        await pipeline.run(event)

    # All fixture events + whatever side-effects were stored
    assert len(store.all_events()) >= len(events)
