"""Tests for the ingestion service webhook endpoints.

All tests mock the Redis stream publisher so no running Redis instance
is needed.  The ingestion logic (signature verification, normalisation,
routing) is fully unit-testable without infrastructure.
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from ingestion.app import create_app

_SECRET = "test-secret"


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient with env vars set and Redis publisher mocked."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", _SECRET)
    return TestClient(create_app())


@patch("ingestion.redis_stream.publish_event", new_callable=AsyncMock)
def test_github_webhook_ignored_event(
    mock_publish: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(monkeypatch)
    body = json.dumps({"zen": "Keep it logically awesome."}).encode()
    resp = client.post(
        "/webhooks/github/",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign(body, _SECRET),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
    mock_publish.assert_not_awaited()


@patch("ingestion.routers.github.settings")
@patch("ingestion.redis_stream.publish_event", new_callable=AsyncMock)
def test_github_webhook_invalid_signature(
    mock_publish: AsyncMock,
    mock_settings: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signature check happens before Redis — 401 without publishing."""
    from unittest.mock import MagicMock
    assert isinstance(mock_settings, MagicMock)
    mock_settings.github_webhook_secret = _SECRET  # type: ignore[attr-defined]
    mock_settings.redis_stream_events = "scrum:events:raw"  # type: ignore[attr-defined]

    client = _make_client(monkeypatch)
    body = json.dumps({"action": "opened"}).encode()
    resp = client.post(
        "/webhooks/github/",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=badsig",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401
    mock_publish.assert_not_awaited()


@patch("ingestion.routers.github.publish_event", new_callable=AsyncMock)
def test_github_webhook_pr_opened_published(
    mock_publish: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid PR opened webhook must be published to the Redis stream."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", _SECRET)
    client = _make_client(monkeypatch)
    payload = {
        "action": "opened",
        "repository": {"full_name": "org/repo"},
        "sender": {"login": "alice"},
        "pull_request": {"number": 42, "title": "feat: new thing"},
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/github/",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body, _SECRET),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    mock_publish.assert_awaited_once()
