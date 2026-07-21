"""Base processor contract.

All processors receive an AgentEvent and return a ProcessorResult.
They are stateless — all state lives in the Sprint Context Store.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from scrumagent_shared.events import AgentEvent


@dataclass
class ProcessorResult:
    """Output of a single processor run.

    enrichments:   key/value pairs added to the event's processed metadata.
    side_effects:  opaque action descriptors consumed by the ActionDispatcher.
    """

    enrichments: dict[str, Any] = field(default_factory=dict)
    side_effects: list[dict[str, Any]] = field(default_factory=list)


class BaseProcessor(ABC):
    """Abstract base for all stateless event processors."""

    @abstractmethod
    async def process(self, event: AgentEvent) -> ProcessorResult:
        """Process one event and return enrichments + side-effects.

        Args:
            event: The normalised AgentEvent to process.

        Returns:
            A ProcessorResult containing enrichments and side-effect descriptors.
        """
        ...
