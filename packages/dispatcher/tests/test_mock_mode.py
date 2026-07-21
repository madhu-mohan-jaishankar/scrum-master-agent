"""Unit tests for ConsoleSink and ActionDispatcher mock mode."""

import pytest
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_dispatcher.sinks.console import ConsoleSink


@pytest.mark.asyncio
async def test_console_sink_send_does_not_raise() -> None:
    sink = ConsoleSink()
    await sink.send(
        {
            "action": "alert",
            "channel": "slack",
            "message": "CI failed on demo-org/api-service.",
        }
    )
    # No assertion needed — just ensure no exception is raised.


@pytest.mark.asyncio
async def test_console_sink_update_does_not_raise() -> None:
    sink = ConsoleSink()
    await sink.update(
        {
            "action": "jira_update",
            "channel": "jira",
            "jira_issue_key": "SCRUM-42",
            "message": "Marked as In Progress.",
        }
    )


@pytest.mark.asyncio
async def test_dispatcher_mock_mode_routes_all_to_console(
    capsys: pytest.CaptureFixture[str],
) -> None:
    dispatcher = ActionDispatcher(mock=True)
    effects = [
        {"action": "alert", "channel": "slack", "message": "Hello Slack"},
        {"action": "jira_update", "channel": "jira", "message": "Jira note"},
        {"action": "email", "channel": "email", "message": "Email body"},
    ]
    await dispatcher.dispatch(effects)
    captured = capsys.readouterr()
    # All three effects should appear in console output.
    assert "ALERT" in captured.out
    assert "Hello Slack" in captured.out
    assert "Jira note" in captured.out
    assert "Email body" in captured.out


@pytest.mark.asyncio
async def test_dispatcher_mock_mode_does_not_call_slack_api() -> None:
    """SlackSink.send() must never be called in mock mode."""
    dispatcher = ActionDispatcher(mock=True)
    # The _slack attribute in mock mode is a ConsoleSink, not a SlackSink.
    from scrumagent_dispatcher.sinks.console import ConsoleSink as CS

    assert isinstance(dispatcher._slack, CS)
    assert isinstance(dispatcher._jira, CS)
