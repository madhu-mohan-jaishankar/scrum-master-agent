"""Unit tests for MockSprintContextStore."""

from pathlib import Path

import pytest
from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_shared.events import AgentEvent, EventSource, EventType


@pytest.fixture()
def store(tmp_path: Path) -> MockSprintContextStore:
    """Return a store seeded from the real fixtures directory."""
    fixtures = Path(__file__).parent.parent.parent.parent / "fixtures"
    return MockSprintContextStore(fixtures_dir=fixtures)


@pytest.mark.asyncio
async def test_store_preloaded_events(store: MockSprintContextStore) -> None:
    events = await store.get_recent_events("SPRINT-42")
    assert len(events) >= 1
    assert all(e["sprint_id"] == "SPRINT-42" for e in events)


@pytest.mark.asyncio
async def test_store_persist_adds_event(store: MockSprintContextStore) -> None:
    before = len(store.all_events())
    event = AgentEvent(
        source=EventSource.GITHUB,
        type=EventType.COMMIT_PUSHED,
        actor="alice",
        sprint_id="SPRINT-42",
    )
    await store.persist_event(event)
    assert len(store.all_events()) == before + 1


@pytest.mark.asyncio
async def test_store_get_snapshot(store: MockSprintContextStore) -> None:
    snap = await store.get_sprint_snapshot("SPRINT-42")
    assert snap is not None
    assert snap["sprint_id"] == "SPRINT-42"
    assert "completed_points" in snap


@pytest.mark.asyncio
async def test_store_missing_sprint_returns_none(store: MockSprintContextStore) -> None:
    snap = await store.get_sprint_snapshot("SPRINT-DOES-NOT-EXIST")
    assert snap is None


@pytest.mark.asyncio
async def test_store_empty_when_no_fixtures(tmp_path: Path) -> None:
    """A store pointed at an empty directory starts empty but doesn't crash."""
    store = MockSprintContextStore(fixtures_dir=tmp_path)
    events = await store.get_recent_events("SPRINT-42")
    assert events == []
    snap = await store.get_sprint_snapshot("SPRINT-42")
    assert snap is None
