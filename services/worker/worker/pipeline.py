"""Event processing pipeline.

The pipeline runs each registered processor against a single AgentEvent,
collects all enrichments and side-effects, persists the event to the Sprint
Context Store, and hands side-effects to the ActionDispatcher.
"""

from __future__ import annotations

import logging
from typing import Any

from scrumagent_context_store.protocol import SprintContextStoreProtocol
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_processors.base import BaseProcessor
from scrumagent_shared.events import AgentEvent

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Runs the ordered processor chain and dispatches side-effects."""

    def __init__(
        self,
        processors: list[BaseProcessor],
        store: SprintContextStoreProtocol,
        dispatcher: ActionDispatcher,
    ) -> None:
        self._processors = processors
        self._store = store
        self._dispatcher = dispatcher

    async def run(self, event: AgentEvent) -> None:
        """Execute the full pipeline for one event.

        Processors run sequentially; failures in one do not skip later ones
        (fail-open strategy for observability during early dev — tighten later).
        """
        all_enrichments: dict[str, Any] = {}
        all_side_effects: list[dict[str, Any]] = []

        for proc in self._processors:
            try:
                result = await proc.process(event)
                all_enrichments.update(result.enrichments)
                all_side_effects.extend(result.side_effects)
            except Exception:
                logger.exception(
                    "Processor %s failed on event %s", proc.__class__.__name__, event.id
                )

        # Persist the event unconditionally for audit / replay.
        try:
            await self._store.persist_event(event)
        except Exception:
            logger.exception("Failed to persist event %s", event.id)

        # Dispatch side-effects.
        if all_side_effects:
            await self._dispatcher.dispatch(all_side_effects)
