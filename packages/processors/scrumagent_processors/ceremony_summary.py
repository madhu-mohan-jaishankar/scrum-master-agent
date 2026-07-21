"""Ceremony Summary Processor.

Generates a structured prose summary for any agile ceremony by reading
the ceremony record from the event payload and calling WatsonX generate().

Supported ceremony types (``ceremony_type`` field in the payload):
    - daily_standup     : per-day status, blockers, action items
    - sprint_review     : demo outcomes, velocity, stakeholder decisions
    - retrospective     : 4Ls / Start-Stop-Continue, action items
    - sprint_planning   : committed scope, capacity, risks
    - all_hands         : highlights, decisions, announcements

If ``ceremony_type`` is unrecognised the processor still attempts a
generic summary so the pipeline never silently drops the event.

Output side-effect action name: ``ceremony_summary``
Output channel:                  ``slack``  (routed to console in mock mode)
"""

from __future__ import annotations

import json
from typing import Any

from scrumagent_shared.events import AgentEvent, EventType
from scrumagent_watsonx.protocol import WatsonxClientProtocol

from scrumagent_processors.base import BaseProcessor, ProcessorResult

# ---------------------------------------------------------------------------
# Ceremony-type → human label used in the prompt and the side-effect message.
# ---------------------------------------------------------------------------
_CEREMONY_LABELS: dict[str, str] = {
    "daily_standup":  "Daily Standup",
    "sprint_review":  "Sprint Review",
    "retrospective":  "Retrospective",
    "sprint_planning": "Sprint Planning",
    "all_hands":      "Engineering All-Hands",
}

# ---------------------------------------------------------------------------
# Prompt templates — each template gets the ceremony record injected as JSON
# so the mock client can match on keyword; the real model uses the full text.
# ---------------------------------------------------------------------------
_PROMPT_TEMPLATE = """\
You are an agile scrum master assistant. Generate a concise, well-structured \
summary of the following {label} ceremony record. Include:
- Key decisions made
- Blockers or risks identified
- Action items with owners
- Any notable metrics (velocity, capacity, demo outcomes, etc.)

Ceremony record (JSON):
{record_json}

Summary:"""


class CeremonySummaryProcessor(BaseProcessor):
    """Generates AI-written summaries for any agile ceremony."""

    def __init__(self, watsonx: WatsonxClientProtocol) -> None:
        self._watsonx = watsonx

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type != EventType.TRIGGER_CEREMONY_SUMMARY:
            return ProcessorResult()

        ceremony: dict[str, Any] = event.payload.get("ceremony", {})
        if not ceremony:
            return ProcessorResult()

        ceremony_type: str = ceremony.get("ceremony_type", "unknown")
        label = _CEREMONY_LABELS.get(ceremony_type, ceremony_type.replace("_", " ").title())
        title = ceremony.get("title", label)
        date = ceremony.get("date", "")
        sprint_id = event.sprint_id or ceremony.get("sprint_id", "")

        # Truncate the record so it fits in the context window budget.
        record_json = json.dumps(ceremony, indent=2)[:3000]
        prompt = _PROMPT_TEMPLATE.format(label=label, record_json=record_json)
        summary_text = self._watsonx.generate(prompt, max_tokens=600)

        date_str = date[:10] if date else "unknown date"
        header = f"*{label} Summary* — {title} ({date_str})"
        if sprint_id:
            header += f"  |  `{sprint_id}`"

        full_message = f"{header}\n\n{summary_text}"

        side_effects: list[dict[str, Any]] = [
            {
                "action": "ceremony_summary",
                "channel": "slack",
                "ceremony_type": ceremony_type,
                "sprint_id": sprint_id,
                "message": full_message,
            }
        ]

        return ProcessorResult(
            enrichments={
                "ceremony_type": ceremony_type,
                "ceremony_title": title,
                "ceremony_date": date_str,
            },
            side_effects=side_effects,
        )
