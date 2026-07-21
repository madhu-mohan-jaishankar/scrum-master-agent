"""Sprint Context Store — Redis JSON + RedisVL vector index.

Data layout in Redis:
  sprint:event:<uuid>        — RedisJSON hash per AgentEvent
  sprint:snapshot:<sprint_id> — RedisJSON hash per sprint health snapshot
  sprint:embeddings           — RedisVL HNSW vector index for text embeddings

Keys use ":" as the Redis namespace separator (de-facto convention).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis.asyncio as aioredis
from scrumagent_shared.events import AgentEvent

logger = logging.getLogger(__name__)

# ── RedisVL schema for the embedding index ────────────────────────────────────
# Defined as a plain dict; redisvl is imported lazily in init_index() so
# the store module can be imported without a live Redis Stack process.
_EMBEDDING_SCHEMA: dict[str, Any] = {
    "index": {
        "name": "sprint_embeddings",
        "prefix": "sprint:emb:",
        "storage_type": "hash",
    },
    "fields": [
        {"name": "sprint_id", "type": "tag"},
        {"name": "text", "type": "text"},
        {
            "name": "embedding",
            "type": "vector",
            "attrs": {
                "dims": 768,
                "distance_metric": "cosine",
                "algorithm": "hnsw",
                "datatype": "float32",
            },
        },
    ],
}

class SprintContextStore:
    """Redis-backed Sprint Context Store using JSON + vector index."""

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or os.environ["REDIS_URL"]
        self._client: aioredis.Redis = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
        )

    # ── Index lifecycle (call once at startup) ────────────────────────────────

    async def init_index(self) -> None:
        """Create the RedisVL vector index if it does not exist.

        Lazily imports redisvl so the module is importable without a
        live Redis Stack process (unit tests, CI, mock mode).

        Safe to call on every startup — redisvl checks existence before creating.
        """
        from redisvl.index import AsyncSearchIndex  # noqa: PLC0415
        from redisvl.schema import IndexSchema  # noqa: PLC0415

        schema = IndexSchema.from_dict(_EMBEDDING_SCHEMA)
        index = AsyncSearchIndex(schema, redis_client=self._client)
        await index.create(overwrite=False)
        logger.info("RedisVL embedding index ready.")

    # ── Write operations ──────────────────────────────────────────────────────

    async def persist_event(self, event: AgentEvent) -> None:
        """Persist a normalised AgentEvent as a Redis JSON string."""
        key = f"sprint:event:{event.id}"
        value = event.model_dump(mode="json")
        # Store as a JSON string under a single field so we can EXPIRE it.
        await self._client.set(key, json.dumps(value), ex=60 * 60 * 24 * 90)  # 90-day TTL

    async def persist_snapshot(self, sprint_id: str, snapshot: dict[str, Any]) -> None:
        """Persist (overwrite) the sprint health snapshot for a sprint."""
        key = f"sprint:snapshot:{sprint_id}"
        await self._client.set(key, json.dumps(snapshot))

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_recent_events(
        self,
        sprint_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Scan sprint:event:* keys and return events matching sprint_id.

        Note: SCAN is O(N) over matching keys — acceptable for sprint-scoped
        volumes.  A secondary index (sorted set keyed by timestamp) can be
        added later for sub-ms range queries at scale.
        """
        results: list[dict[str, Any]] = []
        async for key in self._client.scan_iter("sprint:event:*", count=500):
            raw = await self._client.get(key)
            if raw is None:
                continue
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("sprint_id") == sprint_id:
                results.append(data)
            if len(results) >= limit:
                break
        results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return results[:limit]

    async def get_sprint_snapshot(self, sprint_id: str) -> dict[str, Any] | None:
        """Return the stored sprint health snapshot or None."""
        key = f"sprint:snapshot:{sprint_id}"
        raw = await self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]
