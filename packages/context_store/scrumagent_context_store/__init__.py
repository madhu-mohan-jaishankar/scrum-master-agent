"""scrumagent_context_store — Sprint Context Store (Redis JSON + vector + mock).

SprintContextStore is imported lazily from the store module to avoid
importing redisvl at package load time (redisvl requires a live Redis Stack).
"""

from scrumagent_context_store.mock_store import MockSprintContextStore
from scrumagent_context_store.protocol import SprintContextStoreProtocol

__all__ = ["SprintContextStore", "MockSprintContextStore", "SprintContextStoreProtocol"]


def __getattr__(name: str) -> object:
    if name == "SprintContextStore":
        from scrumagent_context_store.store import SprintContextStore

        return SprintContextStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
