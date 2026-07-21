"""Ingestion service configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_events: str = "scrum:events:raw"

    # ── Webhook secrets ───────────────────────────────────────────────────────
    github_webhook_secret: str = ""
    jira_webhook_secret: str = ""


settings = Settings()
