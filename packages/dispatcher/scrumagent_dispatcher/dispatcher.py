"""Action Dispatcher — routes side-effect descriptors to output channels.

A side-effect descriptor produced by a processor looks like:
    {
        "action": "alert" | "post_digest" | "jira_update" | "standup_digest",
        "channel": "slack" | "jira" | "console",
        "message": "...",
    }

In the PoC (mock=True, the default) all channels route to ConsoleSink so
output is visible in the terminal without any external services.  Pass
concrete SlackSink / JiraSink instances with mock=False to wire real
integrations.
"""

from __future__ import annotations

from typing import Any

from scrumagent_dispatcher.sinks.console import ConsoleSink


class ActionDispatcher:
    """Routes processor side-effects to the correct output sink."""

    def __init__(
        self,
        slack: Any = None,
        jira: Any = None,
        mock: bool = True,
    ) -> None:
        if mock:
            console = ConsoleSink()
            self._slack: Any = console
            self._jira: Any = console
            self._console: ConsoleSink | None = console
        else:
            self._slack = slack
            self._jira = jira
            self._console = None

    async def dispatch(self, side_effects: list[dict[str, Any]]) -> None:
        """Dispatch a list of side-effect descriptors."""
        for effect in side_effects:
            if self._console is not None:
                await self._console.send(effect)
                continue
            channel = effect.get("channel", "")
            match channel:
                case "slack":
                    if self._slack is not None:
                        await self._slack.send(effect)
                case "jira":
                    if self._jira is not None:
                        await self._jira.update(effect)
