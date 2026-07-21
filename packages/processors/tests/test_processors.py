"""Unit tests for stateless event processors."""

from unittest.mock import MagicMock

import pytest
from scrumagent_processors.ci_monitor import CIMonitorProcessor, _is_flaky
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_shared.events import AgentEvent, EventSource, EventType

# ── CI Monitor ────────────────────────────────────────────────────────────────


def test_is_flaky_detects_alternating_pattern() -> None:
    history = [True, False, True, False, True]
    assert _is_flaky(history) is True


def test_is_flaky_rejects_stable_pattern() -> None:
    history = [True, True, True, True, True]
    assert _is_flaky(history) is False


@pytest.mark.asyncio
async def test_ci_monitor_failed_emits_alert() -> None:
    proc = CIMonitorProcessor()
    event = AgentEvent(
        source=EventSource.CI,
        type=EventType.CI_FAILED,
        repo="org/repo",
        payload={"workflow_run": {"name": "test"}},
    )
    result = await proc.process(event)
    assert any(e["action"] == "alert" for e in result.side_effects)


# ── PR Classifier ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pr_classifier_labels_blocking() -> None:
    mock_wx = MagicMock()
    mock_wx.classify.return_value = "blocking"
    proc = PRClassifierProcessor(mock_wx)
    event = AgentEvent(
        source=EventSource.GITHUB,
        type=EventType.PR_COMMENT,
        repo="org/repo",
        actor="alice",
        payload={"comment": {"body": "This will break prod."}, "pull_request": {"number": 7}},
    )
    result = await proc.process(event)
    assert result.enrichments["pr_comment_label"] == "blocking"
    assert any(e["action"] == "alert" for e in result.side_effects)


@pytest.mark.asyncio
async def test_pr_classifier_skips_non_comment_events() -> None:
    mock_wx = MagicMock()
    proc = PRClassifierProcessor(mock_wx)
    event = AgentEvent(
        source=EventSource.GITHUB,
        type=EventType.PR_OPENED,
        repo="org/repo",
    )
    result = await proc.process(event)
    assert result.enrichments == {}
    mock_wx.classify.assert_not_called()
