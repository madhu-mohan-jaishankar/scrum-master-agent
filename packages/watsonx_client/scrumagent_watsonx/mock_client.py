"""Mock WatsonX AI client — returns deterministic canned responses.

Use when SCRUMAGENT_MOCK=1 or in any test that does not need a real model.
Responses are keyed by keywords in the prompt so different call-sites get
distinct, realistic-looking output without any network traffic.
"""

from __future__ import annotations

# ── Canned classify responses ─────────────────────────────────────────────────
# Keyed by (keyword_in_prompt_lower → label).  First match wins.
_CLASSIFY_RULES: list[tuple[str, str]] = [
    # PR comment classification — blocking
    ("break", "blocking"),
    ("must fix", "blocking"),
    ("required", "blocking"),
    ("security", "blocking"),
    ("vulnerability", "blocking"),
    ("crash", "blocking"),
    ("memory leak", "blocking"),
    ("data loss", "blocking"),
    ("regression", "blocking"),
    # PR comment classification — nit
    ("nit", "nit"),
    ("nitpick", "nit"),
    ("style", "nit"),
    ("whitespace", "nit"),
    ("typo", "nit"),
    ("rename", "nit"),
    ("naming", "nit"),
    # PR comment classification — suggestion
    ("suggestion", "suggestion"),
    ("consider", "suggestion"),
    ("could", "suggestion"),
    ("maybe", "suggestion"),
    ("performance", "suggestion"),
    ("optimis", "suggestion"),
    # PR comment classification — question
    ("question", "question"),
    ("why", "question"),
    ("what", "question"),
    ("how does", "question"),
    # Commit classification
    ("feat:", "feature"),
    ("feature:", "feature"),
    ("fix:", "bugfix"),
    ("bugfix:", "bugfix"),
    ("bug:", "bugfix"),
    ("hotfix:", "bugfix"),
    ("refactor:", "refactor"),
    ("refactor", "refactor"),
    ("chore:", "chore"),
    ("docs:", "chore"),
    ("ci:", "chore"),
    ("build:", "chore"),
    ("test:", "chore"),
    ("architectural", "architectural"),
    ("migrate", "architectural"),
    ("restructure", "architectural"),
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
sprint is AT RISK — projected Day 9 (1 day over) due to unplanned scope addition.

**Blockers** — PR #101 has a blocking review comment from bob (iOS layout). \
CI is FLAKY on demo-org/api-service (unit-tests — 3 alternations in 5 runs). \
SCRUM-112 (security: API key rotation, 8 pts) added mid-sprint without capacity swap.

**Today's Focus** — Resolve PR #101 blocker (alice); stabilise flaky CI (bob); \
carol to land batch inference branch; eve to confirm SCRUM-112 scope impact."""

_RETRO_DRAFT = """\
## What Went Well
• Daily async standups kept everyone aligned without meetings.
• CI pipeline failures caught regressions early (3 prevented in this sprint).
• Embedding pipeline (SCRUM-101) shipped on time — great cross-team effort.
• Flaky CI detection surfaced a recurring test-suite issue before it caused \
a missed deploy.

## What To Improve
• Two PRs sat approved-but-unmerged for >2 days — need a merge SLA.
• Sprint commitment was 40 pts but effective capacity was ~32 pts (PTO not accounted).
• Scope creep: SCRUM-112 (8 pts, security) added Day 4 without removing anything.
• New team member (frank) blocked on repo access for 2 days — onboarding gap.

## Action Items
• Tech lead: enforce a 48-hour merge SLA for approved PRs (automate reminder).
• Scrum Master: integrate PTO calendar into sprint capacity calculation.
• Team: no new tickets after Day 1 without a formal scope-swap removal.
• Engineering manager: create onboarding checklist including repo access setup.
• Product: define urgent/security ticket intake process with explicit scope-swap step."""

_RELEASE_NOTES_42 = """\
## v1.4.0 — Sprint 42 Release Notes  ·  2025-07-25

## New Features
• **Dark mode** — the web UI now supports dark mode, automatically honouring the OS-level system preference with a manual override toggle.
• **Embedding pipeline batch inference** — the ML pipeline can now process an entire sprint's data in a single pass, powering faster retrospective clustering.

## Bug Fixes
• Fixed a mobile layout regression on iOS Safari introduced by the dark-mode CSS changes (affected portrait view on all iPhone models).
• Resolved a race condition in the API rate-limiter that caused intermittent HTTP 429 errors under concurrent load.

## Infrastructure
• CI false-positive rate reduced to near zero after identifying shared mutable state in test fixtures as the root cause of flakiness.

## Carried Over
• **SCRUM-112** — Security: API key rotation (8 pts). Added mid-sprint on Day 2; insufficient remaining capacity. **Priority #1 in Sprint 43.**"""

_RELEASE_NOTES_43 = """\
## v1.5.0 — Sprint 43 Release Notes  ·  2025-08-08

## Security
• **API key rotation** — all credentials exposed in the July security incident have been rotated and automated secret-scanning enforcement has been added to CI, preventing future leaks.

## New Features
• **Merge SLA bot** — a Slack reminder is automatically posted when an approved pull request has not been merged within 48 hours, eliminating the stale-PR accumulation seen in Sprint 42.
• **PTO-aware sprint capacity** — sprint planning now pulls PTO data from the company calendar and automatically reduces team capacity, preventing the over-commitment that caused Sprint 42 to run over.

## Bug Fixes
• Eliminated intermittent CI failures by removing shared state from test fixtures; the CI pipeline now passes reliably on every run.

## Infrastructure
• New onboarding checklist and repo-access guide reduce new-joiner setup time from two days to under two hours."""

# Keep the old alias so existing generate rules resolve correctly.
_RELEASE_NOTES = _RELEASE_NOTES_42

_STALE_PR_SCAN = """\
**Stale PR Report** — 2025-07-16

The following pull requests have been approved and CI-green for more than 48 hours \
but are not yet merged:

• `demo-org/ml-pipeline` PR #88 — "refactor: clean up batch job runner" \
  (dave, approved Day 0, 3 days open)

**Recommended action:** Assign a merge owner and merge within 24 hours, \
or add a comment explaining the hold. \
Unmerged approved PRs increase rebase friction for all active branches."""

_SPRINT_PLANNING = """\
**Sprint 43 Planning Summary** — Hardening Sprint

**Capacity** — 5 engineers × 8 days = 40 dev-days. \
Effective capacity after PTO buffer (20 %): 32 dev-days ≈ 36 story points.

**Recommended Backlog** (priority order):
1. SCRUM-112 Security: rotate API keys after token leak — 8 pts (carry over, urgent)
2. SCRUM-107 Logging improvements — 5 pts (carry over, dave)
3. SCRUM-115 Auth-service repo access & onboarding doc — 3 pts (frank unblocked)
4. SCRUM-116 Merge SLA automation (Slack reminder bot) — 5 pts
5. SCRUM-117 PTO calendar sprint capacity integration — 8 pts
6. SCRUM-118 Flaky CI root cause fix for api-service unit-tests — 5 pts
7. SCRUM-119 Dark mode: address remaining nit (variable rename) — 2 pts

**Total:** 36 pts. No scope buffer — treat Day 1 as the last day for additions."""

# ── Ceremony summary canned responses ─────────────────────────────────────────

_CEREMONY_STANDUP = """\
**Daily Standup Summary** — Day 3 of Sprint 42

**Status**
• Alice: PR #101 in review; addressing iOS layout blocker. On track.
• Bob: Rate-limiter fix branch pushed; waiting for CI green and alice re-review.
• Carol: SCRUM-101 (embedding pipeline) complete ✓. Batch inference in progress.
• Dave: PR #88 approved 3 days ago — will merge today.
• Eve: Added SCRUM-112 (security, 8 pts) mid-sprint; scope-swap discussion tomorrow.

**Blockers**
• PR #101 — iOS layout fix needed before merge (alice → bob re-review chain).
• SCRUM-112 unplanned addition puts sprint at risk (projected Day 9, 1 over).

**Today's Action Items**
• Dave → merge PR #88 before EOD.
• Eve → facilitate scope-swap discussion at tomorrow's standup.
• Alice → push iOS fix and re-request review from bob."""

_CEREMONY_SPRINT_REVIEW = """\
**Sprint 42 Review Summary**

**Velocity**
• Committed: 40 pts | Completed: 32 pts | Carried over: 8 pts (80 % completion)
• Carry-over: SCRUM-112 (security key rotation) — priority #1 in Sprint 43.

**Demo Outcomes**
• ✅ Dark mode toggle (SCRUM-103) — accepted by stakeholders; shipping to production.
• ✅ Embedding pipeline batch inference (SCRUM-101) — accepted; scope expansion planned for Sprint 43.
• ✅ Batch job runner refactor (PR #88) — accepted; internal improvement.
• ❌ Security: API key rotation (SCRUM-112) — not ready; carries to Sprint 43 as P0.

**Key Decisions**
• Dark mode and embedding pipeline cleared for production release.
• SCRUM-112 is Sprint 43 hard deadline — no negotiation on scope.
• Batch inference scope expansion added to Sprint 43 backlog."""

_CEREMONY_RETRO = """\
**Sprint 42 Retrospective Summary** (4Ls format)

**Liked**
• Async standup format eliminated ~3 hours of meeting overhead.
• Flaky CI auto-detection surfaced a recurring pipeline issue before it caused missed deploys.
• Embedding pipeline shipped on schedule despite mid-sprint scope pressure.

**Learned**
• Scope additions without a formal swap process directly caused delivery risk.
• New team members need repo access provisioned before sprint day 1.
• Approved-but-unmerged PRs create downstream rebase friction.

**Lacked**
• Merge SLA — PR #88 sat approved for 3 days without action.
• Capacity buffer for urgent/security tickets (SCRUM-112 blindsided the team).
• Structured onboarding checklist (frank was blocked days 1–2).

**Longed For**
• PTO-aware sprint capacity calculator integrated into planning.
• Automated Slack nudge: PR approved but not merged for >48 h.
• Security ticket fast-track process with mandatory scope-swap trade.

**Action Items**
• tech_lead → Automate 48 h merge SLA Slack reminder (by Sprint 43 Day 2).
• eve → Integrate PTO calendar into capacity planning (before Sprint 43 planning).
• eng_mgr → Publish and distribute onboarding checklist (before Sprint 43 Day 1).
• product_mgr → Define security ticket intake + scope-swap process (Sprint 43 Day 1)."""

_CEREMONY_SPRINT_PLANNING = """\
**Sprint 43 Planning Summary** — Hardening Sprint

**Capacity**
• 6 engineers × 8 days = 48 dev-days gross.
• Less 4 PTO days → 44 effective dev-days ≈ 36 story points committed.

**Committed Scope** (36 pts total)
• SCRUM-112 Security: API key rotation — 8 pts | bob | 🔴 URGENT
• SCRUM-107 Logging improvements — 5 pts | dave | 🟠 High
• SCRUM-115 Auth-service repo access + onboarding — 3 pts | frank | 🟠 High
• SCRUM-116 Merge SLA automation (Slack bot) — 5 pts | alice | 🟡 Medium
• SCRUM-117 PTO calendar capacity integration — 8 pts | eve | 🟡 Medium
• SCRUM-118 Flaky CI root cause fix — 5 pts | bob | 🟡 Medium
• SCRUM-119 Dark mode variable rename — 2 pts | alice | 🟢 Low

**Risks**
• Bob owns both SCRUM-112 (urgent) and SCRUM-118 (medium) — may need capacity split.
• SCRUM-117 depends on external PTO API access approval not yet confirmed.

**Team Agreements**
• No new tickets accepted after Day 1 without a points trade.
• Frank unblocked Day 1 via new onboarding checklist.
• Eve will distribute PTO-aware capacity sheet before kickoff."""

_CEREMONY_ALL_HANDS = """\
**Engineering All-Hands Summary** — July 2025

**Highlights**
• Embedding pipeline shipped to production — first ML feature live in the platform.
• API key exposure detected by automated secret scanning; SCRUM-112 (key rotation) in progress.
• Team expanded to 6 engineers: welcome Frank Li!
• CI stability improved — flaky test detection reduced false-failure noise by ~40 %.

**Key Decisions**
• Security posture review added as a standing all-hands agenda item going forward.
• Onboarding checklist approved as official process starting Sprint 43.
• Q3 north star: ship AI-assisted code review to all repositories by end of quarter.

**Announcements**
• Sprint 43 is a hardening sprint focused on security (SCRUM-112) and tech debt.
• All-hands moves to bi-weekly cadence starting August.

**Q3 Engineering OKR Status**
• Platform reliability: on track. AI features: ahead. Security posture: needs attention (SCRUM-112)."""

_GENERATE_RULES: list[tuple[str, str]] = [
    # ── Ceremony summaries (most specific — must come before generic keywords) ──
    # The CeremonySummaryProcessor injects `ceremony_type` literally into the
    # prompt, so these underscore/space variants match before "standup" etc.
    ("daily_standup", _CEREMONY_STANDUP),
    ("daily standup ceremony", _CEREMONY_STANDUP),
    ("sprint_review", _CEREMONY_SPRINT_REVIEW),
    ("sprint review ceremony", _CEREMONY_SPRINT_REVIEW),
    ("4ls", _CEREMONY_RETRO),
    ("sprint_planning", _CEREMONY_SPRINT_PLANNING),
    ("sprint planning ceremony", _CEREMONY_SPRINT_PLANNING),
    ("all_hands", _CEREMONY_ALL_HANDS),
    ("all hands ceremony", _CEREMONY_ALL_HANDS),
    ("engineering all-hands", _CEREMONY_ALL_HANDS),
    # ── Retrospective variants (ceremony retro beats generic retro) ──────────
    ("retrospective ceremony", _CEREMONY_RETRO),
    # ── Release notes (version tags only — most specific, must beat everything) ──
    ("release note v1.5.0", _RELEASE_NOTES_43),
    ("release note v1.4.0", _RELEASE_NOTES_42),
    ("v1.5.0", _RELEASE_NOTES_43),
    ("v1.4.0", _RELEASE_NOTES_42),
    ("release note", _RELEASE_NOTES),
    # ── Scheduled-trigger generate prompts ───────────────────────────────────
    ("pre-standup", _PRE_STANDUP_BRIEF),
    ("pre standup", _PRE_STANDUP_BRIEF),
    ("sprint health", _PRE_STANDUP_BRIEF),
    ("standup digest", _STANDUP_DIGEST),
    ("standup update", _STANDUP_DIGEST),
    ("daily update", _STANDUP_DIGEST),
    ("standup", _STANDUP_DIGEST),
    ("retro", _RETRO_DRAFT),
    ("retrospective", _RETRO_DRAFT),
    ("stale pr", _STALE_PR_SCAN),
    ("stale_pr", _STALE_PR_SCAN),
    ("sprint plan", _SPRINT_PLANNING),
    ("planning", _SPRINT_PLANNING),
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
