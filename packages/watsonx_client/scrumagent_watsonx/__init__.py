"""scrumagent_watsonx — WatsonX AI inference client (real + mock).

WatsonxClient is imported lazily to avoid loading ibm-watsonx-ai at
package import time (not installed in the mock/test environment).
"""

from scrumagent_watsonx.mock_client import MockWatsonxClient
from scrumagent_watsonx.protocol import WatsonxClientProtocol

__all__ = ["WatsonxClient", "MockWatsonxClient", "WatsonxClientProtocol"]


def __getattr__(name: str) -> object:
    if name == "WatsonxClient":
        from scrumagent_watsonx.client import WatsonxClient

        return WatsonxClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
