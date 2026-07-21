"""Activity Aggregator Processor.

Aggregates all event types for a given actor into a rolling activity
window used by the standup digest generator and WIP tracker.

This is the last processor in the enrichment chain; it writes the
enriched activity record to the Sprint Context Store.
"""

from __future__ import annotations

from scrumagent_shared.events import AgentEvent

from scrumagent_processors.base import BaseProcessor, ProcessorResult


class ActivityAggregatorProcessor(BaseProcessor):
    """Aggregates per-actor activity for standup digest consumption."""

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if not event.actor:
            return ProcessorResult()

        # Enrichments surface the actor + event in a structured way so the
        # downstream standup generator can find them via Sprint Context Store.
        enrichments = {
            "activity_actor": event.actor,
            "activity_event_type": event.type.value,
            "activity_repo": event.repo,
        }

        return ProcessorResult(enrichments=enrichments)
