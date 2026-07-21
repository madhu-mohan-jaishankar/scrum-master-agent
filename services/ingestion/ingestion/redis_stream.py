"""Redis Streams publisher for the ingestion service.

Replaces the Kafka producer.  Events are published with XADD to a
single Redis stream (REDIS_STREAM_EVENTS).  The worker reads from
this stream using a consumer group (XREADGROUP).

redis-py's async client is used throughout so no separate async library
is needed.
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from ingestion.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return the singleton async Redis client, connecting if necessary."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def publish_event(event_dict: dict[str, object]) -> None:
    """Publish a serialised AgentEvent dict to the Redis stream.

    Uses XADD with MAXLEN to cap the stream at a reasonable size
    and prevent unbounded memory growth.

    Args:
        event_dict: AgentEvent serialised via model_dump(mode="json").
    """
    client = await get_redis()
    await client.xadd(
        settings.redis_stream_events,
        {"data": json.dumps(event_dict)},
        maxlen=10_000,
        approximate=True,
    )


async def close_redis() -> None:
    """Close the singleton Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
