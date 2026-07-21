"""In-memory mock Sprint Context Store.

Pre-seeded from fixtures/sprint.json and fixtures/events.json.
No Postgres, no pgvector, no database connection required.

Used when SCRUMAGENT_MOCK=1 and in unit tests that exercise store-dependent
logic without setting up a database container.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from scrumagent_shared.events import AgentEvent

logger = logging.getLogger(__name__)

# Default fixture paths — overridable for testing.
_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent.parent / "fixtures"


class MockSprintContextStore:
    """Fully in-memory store pre-seeded from fixture files."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        root = fixtures_dir or _FIXTURES_DIR
        self._events: list[dict[str, Any]] = []
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._sprint_meta: dict[str, Any] = {}
        self._load_fixtures(root)

    # ── Fixture loading ────────────────────────────────────────────────────────

    def _load_fixtures(self, root: Path) -> None:
        events_file = root / "events.json"
        sprint_file = root / "sprint.json"
        snapshots_file = root / "snapshots.json"

        if events_file.exists():
            raw: list[dict[str, Any]] = json.loads(events_file.read_text())
            # Normalise to plain dicts matching get_recent_events output shape.
            for item in raw:
                self._events.append(
                    {
                        "id": item.get("id", ""),
                        "source": item.get("source", ""),
                        "type": item.get("type", ""),
                        "actor": item.get("actor"),
                        "repo": item.get("repo"),
                        "sprint_id": item.get("sprint_id"),
                        "timestamp": item.get("timestamp", ""),
                        "payload": item.get("payload", {}),
                    }
                )
            logger.debug("MockStore: loaded %d events", len(self._events))

        if sprint_file.exists():
            self._sprint_meta = json.loads(sprint_file.read_text())

        if snapshots_file.exists():
            raw_snaps: list[dict[str, Any]] = json.loads(snapshots_file.read_text())
            for snap in raw_snaps:
                self._snapshots[snap["sprint_id"]] = snap

        if not self._snapshots and self._sprint_meta:
            # Synthesise a snapshot from sprint.json so the pipeline has data.
            sprint = self._sprint_meta.get("sprint", {})
            sid = sprint.get("id", "SPRINT-42")
            self._snapshots[sid] = {
                "sprint_id": sid,
                "sprint_name": sprint.get("name", sid),
                "sprint_day": 3,
                "sprint_total_days": 8,
                "total_points": sprint.get("total_points", 40.0),
                "committed_points": sprint.get("committed_points", 40.0),
                "completed_points": 14.0,
                "in_progress_points": 12.0,
                "wip_count": 4,
                "scope_creep_points": 2.0,
                "projected_completion": "on track (Day 7)",
                "blockers": [
                    "PR #101 blocked: iOS layout concern (bob → alice)",
                    "CI failing on demo-org/api-service (unit-tests)",
                ],
                "stale_prs": [
                    "PR #88 demo-org/ml-pipeline — approved 3 days ago, not merged",
                ],
                "ci_failures": [
                    "demo-org/api-service / unit-tests — failed 2025-07-14T11:00Z",
                ],
            }

    # ── Protocol methods ───────────────────────────────────────────────────────

    async def persist_event(self, event: AgentEvent) -> None:
        """Append to the in-memory event log (no-op persistence)."""
        self._events.append(
            {
                "id": str(event.id),
                "source": event.source.value,
                "type": event.type.value,
                "actor": event.actor,
                "repo": event.repo,
                "sprint_id": event.sprint_id,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
            }
        )

    async def get_recent_events(
        self,
        sprint_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return in-memory events filtered by sprint_id."""
        filtered = [e for e in self._events if e.get("sprint_id") == sprint_id]
        return filtered[-limit:]

    async def get_sprint_snapshot(self, sprint_id: str) -> dict[str, Any] | None:
        """Return the pre-built sprint snapshot or None."""
        return self._snapshots.get(sprint_id)

    # ── Extra helpers (mock-only) ──────────────────────────────────────────────

    def all_events(self) -> list[dict[str, Any]]:
        """Return all stored events (useful in tests)."""
        return list(self._events)
