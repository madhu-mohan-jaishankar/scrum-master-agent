"""Abstract base (Protocol) for the Sprint Context Store.

Both SprintContextStore (real, Redis) and MockSprintContextStore
(in-memory) implement this interface so processors and the pipeline
never import the concrete class that requires a Redis connection.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from scrumagent_shared.events import AgentEvent


@runtime_checkable
class SprintContextStoreProtocol(Protocol):
    """Minimal persistence interface used by processors and the pipeline."""

    async def persist_event(self, event: AgentEvent) -> None:
        """Persist a normalised AgentEvent."""
        ...

    async def get_recent_events(
        self,
        sprint_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return the most recent events for a sprint as plain dicts."""
        ...

    async def get_sprint_snapshot(
        self,
        sprint_id: str,
    ) -> dict[str, Any] | None:
        """Return the latest sprint health snapshot or None."""
        ...
