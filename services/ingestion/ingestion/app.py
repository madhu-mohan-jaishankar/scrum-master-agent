"""FastAPI application factory for the ingestion service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ingestion.redis_stream import close_redis
from ingestion.routers import github


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the Redis client lifecycle."""
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScrumAgent Ingestion Service",
        description="Receives and normalises webhook events from GitHub, Jira, and Slack.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(github.router)
    return app


app = create_app()
