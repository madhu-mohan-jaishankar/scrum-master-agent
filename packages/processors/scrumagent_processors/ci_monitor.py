"""CI Monitor Processor.

Tracks CI outcome events and detects flakiness patterns.
A pipeline is considered flaky when it has alternated pass/fail at least
twice in the last 5 runs for the same repo + workflow combination.
"""

from __future__ import annotations

from scrumagent_shared.events import AgentEvent, EventType

from scrumagent_processors.base import BaseProcessor, ProcessorResult

# In-process flakiness window — keyed by (repo, workflow_name)
# Replaced by a Redis sorted set in production for multi-replica safety.
_ci_history: dict[tuple[str, str], list[bool]] = {}
_FLAKINESS_WINDOW = 5
_FLAKINESS_MIN_ALTERNATIONS = 2


class CIMonitorProcessor(BaseProcessor):
    """Monitors CI outcomes and emits flakiness alerts."""

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type not in (EventType.CI_PASSED, EventType.CI_FAILED):
            return ProcessorResult()

        repo = event.repo or "unknown"
        workflow = event.payload.get("workflow_run", {}).get("name", "default")
        key = (repo, workflow)

        passed = event.type == EventType.CI_PASSED
        history = _ci_history.setdefault(key, [])
        history.append(passed)
        if len(history) > _FLAKINESS_WINDOW:
            history.pop(0)

        flaky = _is_flaky(history)
        enrichments = {"ci_flaky": flaky, "ci_workflow": workflow}
        side_effects = []

        if event.type == EventType.CI_FAILED:
            side_effects.append(
                {
                    "action": "alert",
                    "channel": "slack",
                    "message": f"CI failed on `{repo}` ({workflow}).",
                }
            )

        if flaky:
            enrichments["ci_flaky"] = True
            side_effects.append(
                {
                    "action": "alert",
                    "channel": "slack",
                    "message": f"Flaky CI detected on `{repo}` ({workflow}).",
                }
            )

        return ProcessorResult(enrichments=enrichments, side_effects=side_effects)


def _is_flaky(history: list[bool]) -> bool:
    """Return True if the history shows enough pass/fail alternations."""
    alternations = sum(
        1 for i in range(1, len(history)) if history[i] != history[i - 1]
    )
    return len(history) >= _FLAKINESS_WINDOW and alternations >= _FLAKINESS_MIN_ALTERNATIONS
