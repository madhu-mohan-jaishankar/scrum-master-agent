"""Action Dispatcher — routes side-effect descriptors to output channels.

A side-effect descriptor produced by a processor looks like:
    {
        "action": "alert" | "post_digest" | "jira_update" | "email",
        "channel": "slack" | "teams" | "email" | "jira",
        "message": "...",
        # channel-specific keys ...
    }

The dispatcher is invoked by the worker after processors finish.
It resolves the right sink (Slack, Jira, …) and calls it.
All sinks are injected so they can be easily mocked in tests.
"""

from __future__ import annotations

from typing import Any

from scrumagent_dispatcher.sinks.console import ConsoleSink
from scrumagent_dispatcher.sinks.jira import JiraSink
from scrumagent_dispatcher.sinks.slack import SlackSink


class ActionDispatcher:
    """Routes processor side-effects to the correct output sink.

    In mock mode (mock=True), all channels are routed to the ConsoleSink
    so output is visible in the terminal without any external services.
    """

    def __init__(
        self,
        slack: SlackSink | None = None,
        jira: JiraSink | None = None,
        mock: bool = False,
    ) -> None:
        if mock:
            console = ConsoleSink()
            self._slack: SlackSink | ConsoleSink = console
            self._jira: JiraSink | ConsoleSink = console
            self._console: ConsoleSink | None = console
        else:
            self._slack = slack or SlackSink()
            self._jira = jira or JiraSink()
            self._console = None

    async def dispatch(self, side_effects: list[dict[str, Any]]) -> None:
        """Dispatch a list of side-effect descriptors.

        Args:
            side_effects: Produced by one or more processor runs.
        """
        for effect in side_effects:
            channel = effect.get("channel", "")
            if self._console is not None:
                # Mock mode: every channel goes to console.
                await self._console.send(effect)
                continue
            match channel:
                case "slack":
                    await self._slack.send(effect)
                case "jira":
                    await self._jira.update(effect)
                case _:
                    # Unknown channel — log and continue (never crash the worker)
                    pass
