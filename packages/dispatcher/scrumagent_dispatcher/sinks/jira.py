"""Jira output sink.

Updates Jira issues and adds comments via the Jira REST API v3.
Credentials loaded from environment — never hardcoded.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class JiraSink:
    """Writes back to Jira issues (comments, status transitions)."""

    def __init__(self) -> None:
        # Loaded lazily in update() so that the dispatcher can be instantiated
        # without Jira credentials present (e.g. in unit tests for other channels).
        self._base_url: str | None = None
        self._auth: tuple[str, str] | None = None

    def _ensure_credentials(self) -> None:
        if self._base_url is None:
            self._base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
            self._auth = (
                os.environ["JIRA_USER_EMAIL"],
                os.environ["JIRA_API_TOKEN"],
            )

    async def update(self, effect: dict[str, Any]) -> None:
        """Apply a Jira update described by the side-effect dict.

        Args:
            effect: Must contain ``jira_issue_key`` and ``jira_comment``.
        """
        self._ensure_credentials()
        issue_key = effect.get("jira_issue_key")
        comment = effect.get("jira_comment") or effect.get("message")
        if not issue_key or not comment:
            return
        url = f"{self._base_url}/rest/api/3/issue/{issue_key}/comment"
        body = {"body": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": comment}]}
        ]}}
        async with httpx.AsyncClient(auth=self._auth, timeout=10.0) as client:
            resp = await client.post(url, json=body)
            if resp.status_code not in (200, 201):
                logger.error("Jira API error %s: %s", resp.status_code, resp.text)
