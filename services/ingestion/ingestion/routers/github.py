"""GitHub webhook router.

Receives GitHub push / PR / CI events, verifies the HMAC-SHA256
signature, normalises into an AgentEvent, and publishes to the
Redis stream.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from scrumagent_shared.adapters.github import normalise_github_webhook

from ingestion.config import settings
from ingestion.redis_stream import publish_event
from ingestion.security import verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/github", tags=["github"])


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header("", alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """Accept a GitHub webhook, verify it, and publish to Redis Streams.

    Returns 202 Accepted immediately — processing is async.
    Returns 401 if the HMAC-SHA256 signature is invalid.
    """
    body = await request.body()

    if not verify_github_signature(body, settings.github_webhook_secret, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = await request.json()
    event = normalise_github_webhook(x_github_event, payload)
    if event is None:
        return {"status": "ignored", "reason": "event type not relevant"}

    await publish_event(event.model_dump(mode="json"))
    logger.info("Published %s event from %s/%s", event.type, event.actor, event.repo)
    return {"status": "accepted", "event_id": str(event.id)}
