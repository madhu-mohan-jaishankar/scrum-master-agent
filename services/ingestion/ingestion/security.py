"""Webhook security helpers.

GitHub signs each payload with HMAC-SHA256 using the shared secret.
We verify this before processing to prevent spoofed payloads.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_github_signature(body: bytes, secret: str, signature_header: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches the payload.

    Args:
        body:              Raw request body bytes.
        secret:            The shared webhook secret configured in GitHub.
        signature_header:  Value of the ``X-Hub-Signature-256`` header.

    Returns:
        True when valid; False otherwise.  Callers must reject the request on False.
    """
    if not secret:
        logger.warning("GitHub webhook secret not configured — skipping signature check.")
        return True   # Allow in dev; enforce via config in production.

    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        return False

    digest = hmac.new(
        secret.encode(), body, digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(
        f"{expected_prefix}{digest}", signature_header
    )
