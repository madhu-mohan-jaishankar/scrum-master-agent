"""scrumagent_processors — stateless event processor functions."""

from scrumagent_processors.activity_aggregator import ActivityAggregatorProcessor
from scrumagent_processors.base import BaseProcessor, ProcessorResult
from scrumagent_processors.ci_monitor import CIMonitorProcessor
from scrumagent_processors.commit_analyser import CommitAnalyserProcessor
from scrumagent_processors.pr_classifier import PRClassifierProcessor
from scrumagent_processors.ticket_tracker import TicketTrackerProcessor

__all__ = [
    "ProcessorResult",
    "BaseProcessor",
    "PRClassifierProcessor",
    "CommitAnalyserProcessor",
    "CIMonitorProcessor",
    "TicketTrackerProcessor",
    "ActivityAggregatorProcessor",
]
