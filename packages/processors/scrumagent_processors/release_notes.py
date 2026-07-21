"""Release Notes Processor.

Generates stakeholder-facing release notes for a sprint by:

1. Collecting all merged PRs and closed tickets from the event payload
   (sourced from ``fixtures/release_items.json`` in mock mode, or built
   live from the Sprint Context Store events in production).
2. Grouping items by classification in priority order:
   security → feature → bugfix → performance → infrastructure →
   refactor/chore (omitted unless user-visible per prompt rules).
3. Rendering the prompt template from ``prompts/release_notes.txt``.
4. Calling ``watsonx.generate()`` and emitting a ``release_notes``
   side-effect destined for Slack (and optionally Jira / email).

Fires on: ``TRIGGER_RELEASE_NOTES``
Output action: ``release_notes``
Output channel: ``slack``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from scrumagent_shared.events import AgentEvent, EventType
from scrumagent_watsonx.protocol import WatsonxClientProtocol

from scrumagent_processors.base import BaseProcessor, ProcessorResult

logger = logging.getLogger(__name__)

# Section order and human labels — security always leads.
_SECTION_ORDER = [
    ("security",       "## 🔒 Security"),
    ("feature",        "## ✨ New Features"),
    ("bugfix",         "## 🐛 Bug Fixes"),
    ("performance",    "## ⚡ Performance"),
    ("architectural",  "## 🏗 Architecture"),
    ("infrastructure", "## 🔧 Infrastructure"),
    # chore / refactor / trivial intentionally last; omitted if not user-visible
    ("refactor",       "## ♻️  Refactor"),
    ("chore",          "## 🔩 Chore"),
    ("trivial",        "## 🔩 Chore"),
]

# Classifications whose items we skip unless explicitly marked user-visible.
_OMIT_BY_DEFAULT = {"chore", "trivial", "refactor"}

# Path to the prompt template — resolved relative to this file at import time.
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "release_notes.txt"


def _load_prompt_template() -> str:
    if _PROMPT_FILE.exists():
        return _PROMPT_FILE.read_text()
    # Fallback inline template if prompts/ dir is absent (e.g., installed package).
    return (
        "Generate stakeholder-facing release notes for {sprint_name} "
        "({version}, {release_date}).\n\nItems:\n{items}\n\nRelease notes:"
    )


def _build_items_text(
    merged_prs: list[dict[str, Any]],
    closed_tickets: list[dict[str, Any]],
    carried_over: list[dict[str, Any]],
) -> str:
    """Group items by classification and return a formatted text block."""
    # Bucket by classification; prefer PR description over ticket summary.
    buckets: dict[str, list[str]] = {k: [] for k, _ in _SECTION_ORDER}

    # Deduplicate by ticket key so a PR + ticket for the same work appears once.
    seen_tickets: set[str] = set()

    for pr in merged_prs:
        cls = pr.get("classification", "chore")
        desc = pr.get("description") or pr.get("title", "")
        tickets = pr.get("tickets", [])
        ticket_ref = f" ({', '.join(tickets)})" if tickets else ""
        for t in tickets:
            seen_tickets.add(t)
        if cls in buckets:
            buckets[cls].append(f"• {desc}{ticket_ref}")

    for ticket in closed_tickets:
        key = ticket.get("key", "")
        if key in seen_tickets:
            continue  # already covered by a PR entry
        cls = ticket.get("classification", "chore")
        summary = ticket.get("summary", key)
        if cls in buckets:
            buckets[cls].append(f"• {summary} ({key})")

    # Render sections — omit empty ones and skip non-user-visible by default.
    lines: list[str] = []
    for cls, heading in _SECTION_ORDER:
        items = buckets.get(cls, [])
        if not items:
            continue
        if cls in _OMIT_BY_DEFAULT:
            # Only include if a PR description indicates user-visible impact.
            user_visible = any(
                any(kw in item.lower() for kw in ("user", "time", "speed", "visible", "reduce", "guide", "hour"))
                for item in items
            )
            if not user_visible:
                continue
        lines.append(heading)
        lines.extend(items)
        lines.append("")

    # Carried-over section.
    if carried_over:
        lines.append("## ⏭  Carried Over")
        for c in carried_over:
            key = c.get("key", "")
            summary = c.get("summary", key)
            pts = c.get("points")
            reason = c.get("reason", "")
            pts_str = f" ({pts} pts)" if pts else ""
            lines.append(f"• **{key}** — {summary}{pts_str}. {reason}")
        lines.append("")

    return "\n".join(lines).strip()


class ReleaseNotesProcessor(BaseProcessor):
    """Generates AI-written release notes from merged PRs and closed tickets."""

    def __init__(self, watsonx: WatsonxClientProtocol) -> None:
        self._watsonx = watsonx
        self._prompt_template = _load_prompt_template()

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type != EventType.TRIGGER_RELEASE_NOTES:
            return ProcessorResult()

        data: dict[str, Any] = event.payload

        sprint_name: str = data.get("sprint_name", event.sprint_id or "")
        version: str     = data.get("version", "")
        release_date: str = data.get("release_date", "")
        merged_prs: list[dict[str, Any]]   = data.get("merged_prs", [])
        closed_tickets: list[dict[str, Any]] = data.get("closed_tickets", [])
        carried_over: list[dict[str, Any]]   = data.get("carried_over_tickets", [])

        if not merged_prs and not closed_tickets:
            logger.warning(
                "ReleaseNotesProcessor: no merged PRs or closed tickets in payload "
                "for sprint %s — skipping.", event.sprint_id
            )
            return ProcessorResult()

        items_text = _build_items_text(merged_prs, closed_tickets, carried_over)

        prompt = self._prompt_template.format(
            sprint_name=sprint_name,
            version=version,
            release_date=release_date,
            items=items_text,
        )

        notes = self._watsonx.generate(prompt, max_tokens=800)

        # Build a compact stats footer.
        feature_count = sum(
            1 for p in merged_prs if p.get("classification") == "feature"
        )
        bugfix_count = sum(
            1 for p in merged_prs if p.get("classification") == "bugfix"
        )
        security_count = sum(
            1 for p in merged_prs if p.get("classification") == "security"
        )
        total_pts = sum(float(t.get("points", 0)) for t in closed_tickets)

        header = (
            f"*Release Notes — {sprint_name}*"
            + (f"  `{version}`" if version else "")
            + (f"  📅 {release_date}" if release_date else "")
        )
        footer = (
            f"\n---\n_{feature_count} feature(s)  ·  "
            f"{bugfix_count} bug fix(es)  ·  "
            f"{security_count} security fix(es)  ·  "
            f"{total_pts:.0f} pts shipped"
            + (f"  ·  {len(carried_over)} carried over" if carried_over else "")
            + "_"
        )

        full_message = f"{header}\n\n{notes}{footer}"

        return ProcessorResult(
            enrichments={
                "release_notes_sprint": sprint_name,
                "release_notes_version": version,
                "release_notes_features": feature_count,
                "release_notes_bugfixes": bugfix_count,
                "release_notes_pts_shipped": total_pts,
            },
            side_effects=[
                {
                    "action": "release_notes",
                    "channel": "slack",
                    "sprint_id": event.sprint_id,
                    "version": version,
                    "message": full_message,
                }
            ],
        )
