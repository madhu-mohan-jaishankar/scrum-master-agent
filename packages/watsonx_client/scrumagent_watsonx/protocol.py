"""Abstract base (Protocol) for WatsonX AI clients.

Both WatsonxClient (real) and MockWatsonxClient implement this interface.
Downstream code types hints against WatsonxClientProtocol so it never
imports the concrete class that requires ibm_watsonx_ai to be installed.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WatsonxClientProtocol(Protocol):
    """Minimal interface used by all processors."""

    def classify(self, prompt: str, max_tokens: int = 50) -> str:
        """Low-latency classification — returns a single label string."""
        ...

    def generate(self, prompt: str, max_tokens: int = 800) -> str:
        """Prose generation — returns a multi-sentence text response."""
        ...
