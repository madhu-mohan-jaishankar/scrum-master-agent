"""Commit Analyser Processor.

Classifies a commit as one of:
  - trivial      : typo fix, comment, whitespace
  - feature      : new capability
  - bugfix       : fixing a defect
  - refactor     : restructuring without behaviour change
  - chore        : build tooling, dependency bumps, CI config
  - architectural: broad structural change

Uses the WatsonX classify() call.
"""

from __future__ import annotations

from typing import Any

from scrumagent_shared.events import AgentEvent, EventType
from scrumagent_watsonx.protocol import WatsonxClientProtocol

from scrumagent_processors.base import BaseProcessor, ProcessorResult

_PROMPT_TEMPLATE = """\
Classify the following git commit message as exactly one of:
trivial, feature, bugfix, refactor, chore, architectural.
Respond with the single label only.

Commit message:
{message}

Label:"""


class CommitAnalyserProcessor(BaseProcessor):
    """Classifies commit messages via WatsonX AI."""

    def __init__(self, watsonx: WatsonxClientProtocol) -> None:
        self._watsonx = watsonx

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type != EventType.COMMIT_PUSHED:
            return ProcessorResult()

        commits: list[dict[str, Any]] = event.payload.get("commits", [])
        if not commits:
            return ProcessorResult()

        # Classify only the head commit (most recent)
        lines = commits[-1].get("message", "").splitlines()
        head_message: str = lines[0] if lines else ""
        if not head_message:
            return ProcessorResult()

        prompt = _PROMPT_TEMPLATE.format(message=head_message[:500])
        label = self._watsonx.classify(prompt, max_tokens=10).lower()

        valid = {"trivial", "feature", "bugfix", "refactor", "chore", "architectural"}
        if label not in valid:
            label = "chore"

        return ProcessorResult(enrichments={"commit_classification": label})
