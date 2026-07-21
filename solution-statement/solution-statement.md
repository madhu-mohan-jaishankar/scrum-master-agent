# Solution Statement

**IBMer watsonx Challenge 2026**
**Team:** Cormac, Mebin, Richard, Claudia, Adeolu, Crown, Ayden, Yosief
**Submission:** WatsonX ScrumMaster Agent

---

## The Problem and Process

Agile teams lose significant productive time every sprint to the overhead of running Scrum itself. Daily standups are slow because nobody has a clear picture of what actually happened since yesterday. Sprint boards drift out of sync with reality — tickets marked "In Progress" while the underlying PR has been approved and sitting unmerged for three days. Blockers go unnoticed until the standup, by which point half a day is already lost. Retrospectives are shallow because nobody can recall the details of a two-week sprint from memory. Planning sessions overcommit because there is no fast, reliable way to factor in team velocity, public holidays, or the complexity distribution of the backlog.

The WatsonX ScrumMaster Agent addresses this directly. It is an AI-powered agent that treats the sprint board as a source of truth that is supposed to be accurate — and continuously reconciles that board against what is actually happening across GitHub, CI pipelines, Jira, and team communication channels.

## Target Users and How They Interact with the Agent

The target users are software engineering teams running Agile sprints — specifically Scrum Masters, tech leads, and individual contributors who lose time each day to ceremony overhead and information gaps. At IBM, this maps directly to delivery teams working across client engagements where sprint hygiene, velocity tracking, and stakeholder communication are ongoing responsibilities.

Users interact with the agent through the tools they already use: Slack or Microsoft Teams for notifications and standup digests, Jira or GitHub Projects for sprint board reconciliation, and a conversational interface for on-demand queries. The agent works in the background and surfaces information proactively — a pre-standup brief arrives 15 minutes before the meeting, stale PR alerts fire when a merged-but-not-closed PR has been sitting for two days, and a scope creep warning triggers when new tickets are added mid-sprint beyond the agreed threshold. No new tooling or workflow changes are required from the team.

## Anticipated Outcomes

Teams using the WatsonX ScrumMaster Agent gain back time at every ceremony touchpoint. Standups become faster because the per-person digest — derived from commits, PR activity, and ticket updates — is already prepared before anyone speaks. Blockers surface earlier because the agent distinguishes between genuinely blocked work (waiting on a dependency) and stalled work (no activity, no stated reason), and escalates each differently. Sprint planning becomes more accurate because the agent pulls historical velocity data, flags stories above the agreed complexity threshold for breakdown, and adjusts available capacity for public holidays falling within the sprint window. Retrospectives produce richer outputs because the agent drafts a structured retro document from the sprint's actual event history, not from memory.

## Productivity Improvement with AI

IBM Bob was used throughout the development of this agent — to synthesise the initial idea from team brainstorm notes, generate the architecture proposal, produce the sprint plan and sub-task breakdown, scaffold the first prototype module, and draft this submission. Bob's ability to hold full project context across a session, generate implementation-ready artefacts from plain-language descriptions, and produce structured documentation from unstructured inputs made it a practical part of the team's workflow at every stage — not a one-off writing tool.

## Time Savings Rationale

The agent's direct impact on team time is measurable at the ceremony level:

| Ceremony / Task | Current time cost | With ScrumMaster Agent | Saving |
|---|---|---|---|
| Daily standup preparation | 10–15 min/person | ~2 min (digest pre-generated) | ~85% |
| Identifying and escalating blockers | Ad hoc, often same-day delay | Real-time, automated flag | Blocker lag eliminated |
| Sprint planning session | 2–3 hours | ~60–90 min with pre-loaded velocity + capacity data | ~50% |
| Retrospective drafting | 45–60 min facilitation + write-up | Agent draft ready at sprint close | ~70% |
| Stale PR follow-up | Manual, inconsistent | Automated nag at configurable threshold | Near 100% |

For a nine-person team running two-week sprints, the aggregate time saving across these touchpoints is estimated at 6–10 hours per sprint — equivalent to more than a full working day returned to the team every cycle, redirected from ceremony administration to engineering work.

---

*Word count: ~500 words (body text, excluding table and header)*
