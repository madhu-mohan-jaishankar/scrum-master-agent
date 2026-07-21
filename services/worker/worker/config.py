"""Worker service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_events: str = "scrum:events:raw"
    redis_consumer_group: str = "scrum-worker"
    redis_consumer_name: str = "worker-1"

    # ── Mock mode ─────────────────────────────────────────────────────────────
    # Set SCRUMAGENT_MOCK=1 to run without Redis, WatsonX, or Slack.
    scrumagent_mock: bool = False


settings = Settings()
