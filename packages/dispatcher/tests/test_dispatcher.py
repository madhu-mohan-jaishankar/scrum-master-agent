"""Unit tests for ActionDispatcher."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from scrumagent_dispatcher.dispatcher import ActionDispatcher


@pytest.mark.asyncio
async def test_dispatcher_routes_to_slack() -> None:
    mock_slack = MagicMock()
    mock_slack.send = AsyncMock()
    mock_jira = MagicMock()
    mock_jira.update = AsyncMock()

    dispatcher = ActionDispatcher(slack=mock_slack, jira=mock_jira)
    effects = [{"action": "alert", "channel": "slack", "message": "CI failed on org/repo."}]
    await dispatcher.dispatch(effects)

    mock_slack.send.assert_awaited_once()
    mock_jira.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_routes_to_jira() -> None:
    mock_slack = MagicMock()
    mock_slack.send = AsyncMock()
    mock_jira = MagicMock()
    mock_jira.update = AsyncMock()

    dispatcher = ActionDispatcher(slack=mock_slack, jira=mock_jira)
    effects = [{"action": "jira_update", "channel": "jira", "jira_issue_key": "SCRUM-1"}]
    await dispatcher.dispatch(effects)

    mock_jira.update.assert_awaited_once()
    mock_slack.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_ignores_unknown_channel() -> None:
    """Unknown channels must not raise — the worker cannot crash."""
    mock_slack = MagicMock()
    mock_slack.send = AsyncMock()
    dispatcher = ActionDispatcher(slack=mock_slack)
    await dispatcher.dispatch([{"action": "email", "channel": "email", "message": "hi"}])
    mock_slack.send.assert_not_awaited()
