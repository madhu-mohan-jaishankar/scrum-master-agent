"""Redis Streams consumer — the main worker loop.

Reads raw events from a Redis stream using XREADGROUP for at-least-once
delivery.  The entry ID is acknowledged (XACK) only after successful
processing so failed events are re-delivered on restart.

Consumer group and consumer name are configurable via environment variables;
multiple worker replicas can share the same group for horizontal scaling.
"""

from __future__ import annotations

import json
import logging
from typing import cast

import redis.asyncio as aioredis
from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_context_store.protocol import SprintContextStoreProtocol
from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor
from scrumagent_processors.ci_monitor import CIMonitorProcessor
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_processors.ticket_tracker import TicketTrackerProcessor
from scrumagent_shared.events import AgentEvent
from scrumagent_watsonx.mock_client import MockWatsonxClient
from scrumagent_watsonx.protocol import WatsonxClientProtocol

from worker.config import settings
from worker.pipeline import ProcessingPipeline

logger = logging.getLogger(__name__)


def _build_pipeline() -> ProcessingPipeline:
    """Construct the processing pipeline with all dependencies wired.

    In mock mode, real WatsonX / Redis store / Slack clients are replaced
    with in-memory or console equivalents — no external services needed.
    """
    wx: WatsonxClientProtocol
    store: SprintContextStoreProtocol
    if settings.scrumagent_mock:
        logger.info("Running in MOCK MODE — no external services required.")
        wx = MockWatsonxClient()
        store = MockSprintContextStore()
        dispatcher = ActionDispatcher(mock=True)
    else:
        from scrumagent_context_store.store import SprintContextStore  # noqa: PLC0415
        from scrumagent_watsonx.client import WatsonxClient  # noqa: PLC0415

        wx = WatsonxClient()
        store = SprintContextStore(settings.redis_url)
        dispatcher = ActionDispatcher()
    processors = [
        PRClassifierProcessor(wx),
        CommitAnalyserProcessor(wx),
        CIMonitorProcessor(),
        TicketTrackerProcessor(),
        ActivityAggregatorProcessor(),
    ]
    return ProcessingPipeline(processors=processors, store=store, dispatcher=dispatcher)


async def _ensure_consumer_group(client: aioredis.Redis) -> None:
    """Create the consumer group if it does not already exist."""
    try:
        await client.xgroup_create(
            settings.redis_stream_events,
            settings.redis_consumer_group,
            id="0",
            mkstream=True,
        )
        logger.info(
            "Created consumer group '%s' on stream '%s'",
            settings.redis_consumer_group,
            settings.redis_stream_events,
        )
    except Exception as exc:
        # BUSYGROUP means it already exists — safe to ignore.
        if "BUSYGROUP" not in str(exc):
            raise


async def consume() -> None:
    """Run the Redis Streams consumer loop indefinitely."""
    pipeline = _build_pipeline()
    client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await _ensure_consumer_group(client)
    logger.info(
        "Worker consumer started — group='%s' stream='%s'",
        settings.redis_consumer_group,
        settings.redis_stream_events,
    )
    try:
        while True:
            # Block for up to 2 s waiting for new entries.
            raw = await client.xreadgroup(
                groupname=settings.redis_consumer_group,
                consumername=settings.redis_consumer_name,
                streams={settings.redis_stream_events: ">"},
                count=10,
                block=2000,
            )
            if not raw:
                continue
            messages = cast(list[tuple[str, list[tuple[str, dict[str, str]]]]], raw)
            for _stream, entries in messages:
                for entry_id, fields in entries:
                    try:
                        event = AgentEvent.model_validate(json.loads(fields["data"]))
                        await pipeline.run(event)
                        await client.xack(
                            settings.redis_stream_events,
                            settings.redis_consumer_group,
                            entry_id,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to process stream entry id=%s", entry_id
                        )
                        # Do not ack — entry will be re-delivered on restart
                        # or reclaimed via XAUTOCLAIM.
    finally:
        await client.aclose()
