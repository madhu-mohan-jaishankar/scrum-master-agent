"""scrumagent_watsonx — WatsonX AI inference client (mock + protocol)."""

from scrumagent_watsonx.mock_client import MockWatsonxClient
from scrumagent_watsonx.protocol import WatsonxClientProtocol

__all__ = ["MockWatsonxClient", "WatsonxClientProtocol"]
