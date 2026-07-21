"""Scheduler service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_events: str = "scrum:events:raw"

    # Active sprint ID injected via environment; updated each sprint start.
    active_sprint_id: str = "sprint-current"

    # Cron expressions (APScheduler format)
    standup_cron_hour: int = 9
    standup_cron_minute: int = 0
    pre_standup_cron_hour: int = 8
    pre_standup_cron_minute: int = 45


settings = Settings()
