"""Scheduled trigger jobs.

Each job publishes an internal AgentEvent to the Redis stream so the worker
handles it via the same processor pipeline as real webhook events.
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis
from scrumagent_shared.events import AgentEvent, EventSource, EventType

from scheduler.config import settings

logger = logging.getLogger(__name__)


async def emit_trigger(event_type: EventType, client: aioredis.Redis) -> None:
    """Publish an internal trigger event to the Redis stream."""
    event = AgentEvent(
        source=EventSource.INTERNAL,
        type=event_type,
        sprint_id=settings.active_sprint_id,
    )
    await client.xadd(
        settings.redis_stream_events,
        {"data": json.dumps(event.model_dump(mode="json"))},
        maxlen=10_000,
        approximate=True,
    )
    logger.info("Emitted trigger %s for sprint %s", event_type, settings.active_sprint_id)


async def trigger_pre_standup(client: aioredis.Redis) -> None:
    await emit_trigger(EventType.TRIGGER_PRE_STANDUP, client)


async def trigger_standup(client: aioredis.Redis) -> None:
    await emit_trigger(EventType.TRIGGER_PRE_STANDUP, client)


async def trigger_stale_pr_scan(client: aioredis.Redis) -> None:
    await emit_trigger(EventType.TRIGGER_STALE_PR_SCAN, client)
