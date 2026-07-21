"""Mock WatsonX AI client — returns deterministic canned responses.

Use when SCRUMAGENT_MOCK=1 or in any test that does not need a real model.
Responses are keyed by keywords in the prompt so different call-sites get
distinct, realistic-looking output without any network traffic.
"""

from __future__ import annotations

# ── Canned classify responses ─────────────────────────────────────────────────
# Keyed by (keyword_in_prompt_lower → label).  First match wins.
_CLASSIFY_RULES: list[tuple[str, str]] = [
    # PR comment classification
    ("break", "blocking"),
    ("must fix", "blocking"),
    ("required", "blocking"),
    ("nit", "nit"),
    ("nitpick", "nit"),
    ("style", "nit"),
    ("suggestion", "suggestion"),
    ("consider", "suggestion"),
    ("question", "question"),
    ("why", "question"),
    # Commit classification
    ("feat:", "feature"),
    ("fix:", "bugfix"),
    ("refactor:", "refactor"),
    ("chore:", "chore"),
    ("docs:", "chore"),
    ("ci:", "chore"),
    ("architectural", "architectural"),
]

_DEFAULT_CLASSIFY = "suggestion"

# ── Canned generate responses ─────────────────────────────────────────────────
# Keyed by keywords in the prompt.
_STANDUP_DIGEST = """\
• Completed: Reviewed PR #101 (dark-mode toggle) and left blocking comment \
on iOS layout issue.
• Working on: Writing unit tests for the API service rate-limiter.
• No blockers — awaiting PR author to address review comment."""

_PRE_STANDUP_BRIEF = """\
**Sprint Health** — Day 3 of 8. Completed 14/40 pts (35 %). At current pace \
finishing on track (projected Day 7).

**Blockers** — PR #101 has a blocking review comment from bob (iOS layout). \
CI is failing on demo-org/api-service (unit-tests workflow).

**Today's Focus** — Resolve PR #101 blocker; fix failing CI; carol to \
progress SCRUM-101 (embedding pipeline, 5 pts)."""

_RETRO_DRAFT = """\
## What Went Well
• Daily async standups kept everyone aligned without meetings.
• CI pipeline failures caught regressions early (3 prevented in this sprint).
• PR review turnaround was under 4 hours on average.

## What To Improve
• Two PRs sat approved-but-unmerged for >2 days — need a merge SLA.
• Sprint commitment was 40 pts but capacity was effectively 32 pts (PTO).
• Scope creep: 2 tickets added on Day 4 without capacity adjustment.

## Action Items
• Tech lead: set a 48-hour merge SLA for approved PRs.
• Scrum Master: add PTO to sprint capacity calculation before planning.
• Team: no new tickets after Day 1 without removing equivalent points."""

_RELEASE_NOTES = """\
## Sprint 42 Release Notes

**New Features**
• Dark mode toggle added to the web UI — respects system preference.
• Embedding pipeline now supports batch inference for retro clustering.

**Bug Fixes**
• Fixed iOS mobile layout breakage introduced in the dark-mode CSS changes.
• Resolved intermittent API rate-limiter failure under concurrent load.

**Infrastructure**
• CI pipeline stabilised — flaky test suite root cause identified and fixed."""

_GENERATE_RULES: list[tuple[str, str]] = [
    # More specific patterns first — order matters.
    ("pre-standup", _PRE_STANDUP_BRIEF),
    ("pre standup", _PRE_STANDUP_BRIEF),
    ("sprint health", _PRE_STANDUP_BRIEF),
    ("standup digest", _STANDUP_DIGEST),
    ("standup update", _STANDUP_DIGEST),
    ("daily update", _STANDUP_DIGEST),
    ("standup", _STANDUP_DIGEST),
    ("retro", _RETRO_DRAFT),
    ("retrospective", _RETRO_DRAFT),
    ("release note", _RELEASE_NOTES),
    ("brief", _PRE_STANDUP_BRIEF),
]

_DEFAULT_GENERATE = (
    "Mock generation response. Replace SCRUMAGENT_MOCK=1 with real "
    "WatsonX credentials to see live model output."
)


class MockWatsonxClient:
    """Deterministic mock — implements WatsonxClientProtocol, needs no API key."""

    def classify(self, prompt: str, max_tokens: int = 50) -> str:  # noqa: ARG002
        """Return the first matching label or the default."""
        lower = prompt.lower()
        for keyword, label in _CLASSIFY_RULES:
            if keyword in lower:
                return label
        return _DEFAULT_CLASSIFY

    def generate(self, prompt: str, max_tokens: int = 800) -> str:  # noqa: ARG002
        """Return a canned prose response matched by keywords in the prompt."""
        lower = prompt.lower()
        for keyword, response in _GENERATE_RULES:
            if keyword in lower:
                return response
        return _DEFAULT_GENERATE
