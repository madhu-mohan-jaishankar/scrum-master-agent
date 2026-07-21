"""scrumagent_dispatcher — action dispatchers for all output channels."""

from scrumagent_dispatcher.dispatcher import ActionDispatcher
from scrumagent_dispatcher.sinks.console import ConsoleSink

__all__ = ["ActionDispatcher", "ConsoleSink"]
