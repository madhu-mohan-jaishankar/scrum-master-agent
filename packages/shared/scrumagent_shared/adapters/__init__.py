"""Normalisation adapters: vendor payload → AgentEvent."""

from scrumagent_shared.adapters.github import normalise_github_webhook
from scrumagent_shared.adapters.jira import normalise_jira_webhook

__all__ = ["normalise_github_webhook", "normalise_jira_webhook"]
