"""Redis key schema and constants for the Sprint Context Store.

No ORM models — Redis keys follow a structured naming convention:

  sprint:event:<uuid>         String (JSON) — persisted AgentEvent
  sprint:snapshot:<sprint_id> String (JSON) — sprint health snapshot
  sprint:emb:<id>             Hash — embedding vectors (managed by RedisVL)

TTLs:
  sprint:event:*              90 days
  sprint:snapshot:*           no expiry (overwritten each standup)
"""

from __future__ import annotations

# Key prefixes — centralised so nothing hard-codes strings outside this file.
KEY_EVENT = "sprint:event:{id}"
KEY_SNAPSHOT = "sprint:snapshot:{sprint_id}"
KEY_EMBEDDING = "sprint:emb:{id}"

# Stream and index names.
STREAM_RAW_EVENTS = "scrum:events:raw"
INDEX_EMBEDDINGS = "sprint_embeddings"

# Event TTL in seconds (90 days).
EVENT_TTL_SECONDS = 60 * 60 * 24 * 90
