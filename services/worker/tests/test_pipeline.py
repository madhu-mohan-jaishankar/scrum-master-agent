"""Unit tests for the processing pipeline."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from scrumagent_processors.base import ProcessorResult
from scrumagent_shared.events import AgentEvent, EventSource, EventType
from worker.pipeline import ProcessingPipeline


@pytest.fixture()
def pipeline() -> Generator[ProcessingPipeline, None, None]:
    mock_proc = MagicMock()
    mock_proc.process = AsyncMock(
        return_value=ProcessorResult(
            enrichments={"test": True},
            side_effects=[{"action": "alert", "channel": "slack", "message": "hi"}],
        )
    )
    mock_store = MagicMock()
    mock_store.persist_event = AsyncMock()
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock()
    yield ProcessingPipeline(
        processors=[mock_proc],
        store=mock_store,
        dispatcher=mock_dispatcher,
    )


@pytest.mark.asyncio
async def test_pipeline_persists_event(pipeline: ProcessingPipeline) -> None:
    event = AgentEvent(source=EventSource.GITHUB, type=EventType.COMMIT_PUSHED, repo="org/r")
    await pipeline.run(event)
    pipeline._store.persist_event.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_pipeline_dispatches_side_effects(pipeline: ProcessingPipeline) -> None:
    event = AgentEvent(source=EventSource.GITHUB, type=EventType.COMMIT_PUSHED)
    await pipeline.run(event)
    pipeline._dispatcher.dispatch.assert_awaited_once()
