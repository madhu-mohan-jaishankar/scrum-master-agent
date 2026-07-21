"""Scheduler service entry point.

Uses APScheduler with a single async Redis client to publish
internal trigger events into the Redis stream.
"""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scheduler.config import settings
from scheduler.jobs import trigger_pre_standup, trigger_stale_pr_scan, trigger_standup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        trigger_pre_standup,
        "cron",
        hour=settings.pre_standup_cron_hour,
        minute=settings.pre_standup_cron_minute,
        day_of_week="mon-fri",
        args=[client],
    )

    scheduler.add_job(
        trigger_standup,
        "cron",
        hour=settings.standup_cron_hour,
        minute=settings.standup_cron_minute,
        day_of_week="mon-fri",
        args=[client],
    )

    scheduler.add_job(
        trigger_stale_pr_scan,
        "cron",
        hour="9-17",
        minute=0,
        day_of_week="mon-fri",
        args=[client],
    )

    scheduler.start()
    logger.info("Scheduler started.")
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
