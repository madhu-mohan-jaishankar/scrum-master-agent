"""Console output sink — pretty-prints side-effects to stdout.

Used in mock mode so the demo output is clearly visible without needing
a live Slack workspace or Jira instance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# ANSI colour codes — degrade gracefully on terminals that don't support them.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BLUE = "\033[34m"
_MAGENTA = "\033[35m"

_ACTION_COLOURS: dict[str, str] = {
    "alert": _RED,
    "post_digest": _GREEN,
    "pre_standup_brief": _CYAN,
    "retro_draft": _MAGENTA,
    "release_notes": _BLUE,
    "jira_update": _YELLOW,
    "standup_digest": _GREEN,
    "ceremony_summary": _CYAN,
    "burndown_chart": _GREEN,
}

_CHANNEL_LABELS: dict[str, str] = {
    "slack": "📢 Slack",
    "jira": "🔵 Jira",
    "email": "📧 Email",
    "console": "🖥  Console",
    "dashboard": "📊 Dashboard",
}


def _ts() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


class ConsoleSink:
    """Prints formatted side-effects to stdout — zero dependencies."""

    async def send(self, effect: dict[str, Any]) -> None:
        """Print a Slack-destined side-effect in a readable format."""
        self._print_effect(effect)

    async def update(self, effect: dict[str, Any]) -> None:
        """Print a Jira-destined side-effect in a readable format."""
        self._print_effect(effect)

    def _print_effect(self, effect: dict[str, Any]) -> None:
        action = effect.get("action", "message")
        channel = effect.get("channel", "console")
        message = effect.get("message", "")

        colour = _ACTION_COLOURS.get(action, _RESET)
        channel_label = _CHANNEL_LABELS.get(channel, f"[{channel}]")

        divider = "─" * 60
        print(f"\n{_BOLD}{colour}{divider}{_RESET}")
        print(
            f"{_BOLD}{colour}[{_ts()}] {action.upper()} → {channel_label}{_RESET}"
        )
        print(f"{divider}")
        if message:
            for line in message.strip().splitlines():
                print(f"  {line}")
        # Print any extra keys (jira_issue_key, slack_channel, etc.)
        extras = {
            k: v
            for k, v in effect.items()
            if k not in ("action", "channel", "message")
        }
        if extras:
            print()
            for k, v in extras.items():
                print(f"  {_BOLD}{k}{_RESET}: {v}")
        print(f"{colour}{divider}{_RESET}\n")
