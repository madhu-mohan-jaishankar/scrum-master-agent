"""PR Classifier Processor.

Classifies pull-request comments as one of:
  - blocking   : must be resolved before merge
  - suggestion : non-blocking improvement idea
  - nit        : trivial style / cosmetic comment
  - question   : author seeking clarification

Uses the WatsonX classify() call (small model, low latency).
"""

from __future__ import annotations

from scrumagent_shared.events import AgentEvent, EventType
from scrumagent_watsonx.protocol import WatsonxClientProtocol

from scrumagent_processors.base import BaseProcessor, ProcessorResult

_CLASSIFY_PROMPT_TEMPLATE = """\
You are a code-review classifier. Given the following pull-request comment,
classify it as exactly one of: blocking, suggestion, nit, question.
Respond with the single label only — no explanation.

Comment:
{comment}

Label:"""


class PRClassifierProcessor(BaseProcessor):
    """Classifies PR comments via WatsonX AI."""

    def __init__(self, watsonx: WatsonxClientProtocol) -> None:
        self._watsonx = watsonx

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type != EventType.PR_COMMENT:
            return ProcessorResult()

        comment_body: str = event.payload.get("comment", {}).get("body", "")
        if not comment_body:
            return ProcessorResult()

        prompt = _CLASSIFY_PROMPT_TEMPLATE.format(comment=comment_body[:1000])
        label = self._watsonx.classify(prompt, max_tokens=10).lower()

        valid_labels = {"blocking", "suggestion", "nit", "question"}
        if label not in valid_labels:
            label = "question"  # safe fallback

        enrichments = {"pr_comment_label": label}
        side_effects = []

        if label == "blocking":
            side_effects.append(
                {
                    "action": "alert",
                    "channel": "slack",
                    "message": (
                        f"Blocking review comment on `{event.repo}` PR "
                        f"#{event.payload.get('pull_request', {}).get('number', '?')} "
                        f"by {event.actor}."
                    ),
                }
            )

        return ProcessorResult(enrichments=enrichments, side_effects=side_effects)
