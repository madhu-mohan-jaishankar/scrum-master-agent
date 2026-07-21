"""Slack output sink.

Posts messages via the Slack Web API using the official slack-sdk.
The bot token is loaded from the environment — never hardcoded.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackSink:
    """Sends messages and alerts to Slack channels."""

    def __init__(self) -> None:
        self._client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self._default_channel = os.environ.get("SLACK_DEFAULT_CHANNEL", "#scrum-bot")

    async def send(self, effect: dict[str, Any]) -> None:
        """Send a side-effect descriptor as a Slack message.

        Args:
            effect: Side-effect dict with at least ``message`` key.
                    Optional ``slack_channel`` overrides the default channel.
        """
        channel = effect.get("slack_channel", self._default_channel)
        text = effect.get("message", "")
        if not text:
            return
        try:
            await self._client.chat_postMessage(channel=channel, text=text)
        except SlackApiError as exc:
            # Log but do not crash the worker — messaging failures must not
            # block event processing.
            logger.error("Slack API error: %s", exc.response["error"])
