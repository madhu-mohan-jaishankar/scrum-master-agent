"""Burndown Chart Processor.

Generates a terminal burndown chart for any sprint that has burndown data
in the event payload.  The chart is computed entirely from the fixture data
(no LLM call needed) and emitted as a ``burndown_chart`` side-effect so it
prints to the console via ConsoleSink in mock mode.

Chart anatomy
─────────────
  Y-axis  : remaining story points  (top = committed, bottom = 0)
  X-axis  : sprint days             (left = Day 1, right = last day)
  ─ ─ ─   : ideal burndown line     (linear, adjusted for scope changes)
  ●        : actual remaining points per completed day
  ◌        : today cursor           (current day, partial progress)
  ▲        : scope creep marker     (points added mid-sprint)

Legend and a one-line status verdict are printed below the chart.
"""

from __future__ import annotations

import math
from typing import Any

from scrumagent_shared.events import AgentEvent, EventType

from scrumagent_processors.base import BaseProcessor, ProcessorResult

# ── Layout constants ──────────────────────────────────────────────────────────
_CHART_WIDTH = 52   # printable columns for the plot area
_CHART_HEIGHT = 14  # rows (Y resolution); each row = points / height range
_H_PAD = 2          # left gutter width (Y-axis labels)

# ANSI helpers — degrade gracefully if the terminal strips escapes.
_R = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"


def _col(code: str, text: str) -> str:
    return f"{code}{text}{_R}"


# ── Chart builder ─────────────────────────────────────────────────────────────

def build_burndown_chart(
    sprint_id: str,
    sprint_name: str,
    total_days: int,
    committed_points: float,
    scope_changes: list[dict[str, Any]],   # [{day, delta, reason}]
    daily_completed: list[dict[str, Any]], # [{day, points, tickets}]
    current_day: int,
) -> str:
    """Return a fully rendered ANSI burndown chart string."""

    # ── 1. Build per-day remaining-points series ──────────────────────────────
    # scope[d] = total points committed *at the start of* day d (1-indexed)
    scope: list[float] = [committed_points] * (total_days + 1)  # index 0 unused
    for sc in scope_changes:
        for d in range(sc["day"], total_days + 1):
            scope[d] += sc["delta"]

    # cumulative completed points after each day
    cum_done: dict[int, float] = {}
    running = 0.0
    for entry in sorted(daily_completed, key=lambda e: e["day"]):
        running += entry["points"]
        cum_done[entry["day"]] = running

    # actual remaining after each completed day
    actual: dict[int, float] = {}
    for d in range(1, total_days + 1):
        if d <= current_day:
            done_so_far = cum_done.get(d, cum_done.get(d - 1, 0.0) if d > 1 else 0.0)
            actual[d] = max(0.0, scope[d] - done_so_far)

    # ideal line: straight from scope[1] on Day 0 to 0 on Day total_days
    # We step it at each day boundary using the scope at that day.
    def ideal(d: float) -> float:
        return max(0.0, scope[min(total_days, math.ceil(max(1, d)))] * (1.0 - (d - 1) / (total_days - 1 + 1e-9)))

    # ── 2. Y-axis range ───────────────────────────────────────────────────────
    max_pts = max(scope[1:total_days + 1]) if scope[1:] else committed_points
    # round up to nearest 5 for cleaner labels
    y_max = math.ceil(max_pts / 5) * 5 or 5

    # ── 3. Coordinate mappers ─────────────────────────────────────────────────
    # map day (1..total_days) → column index (0..CHART_WIDTH-1)
    def day_to_col(d: float) -> int:
        return round((d - 1) / (total_days - 1 + 1e-9) * (_CHART_WIDTH - 1))

    # map points → row index (0 = top, CHART_HEIGHT-1 = bottom)
    def pts_to_row(pts: float) -> int:
        frac = 1.0 - pts / y_max
        return min(_CHART_HEIGHT - 1, max(0, round(frac * (_CHART_HEIGHT - 1))))

    # ── 4. Build the grid ─────────────────────────────────────────────────────
    # grid[row][col] = (char, colour_code)
    grid: list[list[tuple[str, str]]] = [
        [(" ", "")] * _CHART_WIDTH for _ in range(_CHART_HEIGHT)
    ]

    def plot(row: int, col: int, ch: str, colour: str) -> None:
        if 0 <= row < _CHART_HEIGHT and 0 <= col < _CHART_WIDTH:
            grid[row][col] = (ch, colour)

    # Ideal line — dashes
    for col in range(_CHART_WIDTH):
        d = 1 + col / (_CHART_WIDTH - 1) * (total_days - 1)
        row = pts_to_row(ideal(d))
        existing_ch = grid[row][col][0]
        if existing_ch == " ":
            plot(row, col, "─", _DIM)

    # Scope-creep markers — vertical ▲ at the day column
    scope_creep_days: set[int] = set()
    for sc in scope_changes:
        col = day_to_col(sc["day"])
        scope_creep_days.add(sc["day"])
        for row in range(_CHART_HEIGHT):
            if grid[row][col][0] in (" ", "─"):
                plot(row, col, "┊", _YELLOW)
        # put a ▲ at the old scope level
        old_scope = scope[sc["day"]] - sc["delta"]
        plot(pts_to_row(old_scope), col, "▲", _YELLOW)

    # Actual line — connect dots with thin lines, then overdraw dots
    prev_col: int | None = None
    prev_row: int | None = None
    for d in range(1, current_day + 1):
        if d not in actual:
            continue
        col = day_to_col(d)
        row = pts_to_row(actual[d])
        # draw connector between consecutive points
        if prev_col is not None and prev_row is not None and col > prev_col:
            for c in range(prev_col + 1, col):
                t = (c - prev_col) / (col - prev_col)
                interp_row = round(prev_row + t * (row - prev_row))
                if grid[interp_row][c][0] in (" ", "─"):
                    plot(interp_row, c, "·", _CYAN)
        is_today = d == current_day
        ch = "◌" if is_today else "●"
        colour = _GREEN if actual[d] <= ideal(d) + 0.5 else _RED
        if is_today:
            colour = _CYAN
        plot(row, col, ch, _BOLD + colour)
        prev_col, prev_row = col, row

    # ── 5. Render to string ───────────────────────────────────────────────────
    lines: list[str] = []

    # Title
    lines.append(
        _col(_BOLD, f"  Burndown — {sprint_name}")
    )
    lines.append("")

    # Y-axis label + grid rows
    for row_i in range(_CHART_HEIGHT):
        pts_at_row = y_max * (1.0 - row_i / (_CHART_HEIGHT - 1))
        # only label every other row to reduce noise
        if row_i % 2 == 0:
            label = f"{pts_at_row:>4.0f} "
        else:
            label = "     "
        row_str = _col(_DIM, label) + _col(_DIM, "│")
        for col_i, (ch, colour) in enumerate(grid[row_i]):
            row_str += f"{colour}{ch}{_R}" if colour else ch
        lines.append(row_str)

    # X-axis
    x_axis = "     └" + "─" * _CHART_WIDTH
    lines.append(_col(_DIM, x_axis))

    # Day labels — every day if room, else every 2
    step = 1 if total_days <= 8 else 2
    label_row = "      "
    for d in range(1, total_days + 1, step):
        col = day_to_col(d)
        # pad to column position
        label_row = label_row.ljust(6 + col) + str(d)
    lines.append(_col(_DIM, label_row))
    lines.append(_col(_DIM, "      " + " " * (_CHART_WIDTH // 2 - 3) + "Day"))
    lines.append("")

    # ── 6. Legend ─────────────────────────────────────────────────────────────
    def leg(sym: str, colour: str, desc: str) -> str:
        return f"  {colour}{sym}{_R}  {desc}"

    lines.append(leg("─ ─", _DIM, "Ideal burndown"))
    lines.append(leg("●", _BOLD + _GREEN, "Actual (on/ahead)") + "   " +
                 leg("●", _BOLD + _RED, "Actual (behind)"))
    lines.append(leg("◌", _BOLD + _CYAN, "Today") + "   " +
                 leg("▲", _YELLOW, "Scope added"))
    lines.append("")

    # ── 7. Scope changes list ─────────────────────────────────────────────────
    if scope_changes:
        lines.append(_col(_YELLOW, "  Scope changes:"))
        for sc in scope_changes:
            sign = "+" if sc["delta"] >= 0 else ""
            sc_day = sc["day"]
            sc_delta = sc["delta"]
            sc_reason = sc.get("reason", "")
            lines.append(
                f"  {_col(_DIM, f'Day {sc_day}:')} "
                f"{_col(_YELLOW, f'{sign}{sc_delta:.0f} pts')} "
                f"{sc_reason}"
            )
        lines.append("")

    # ── 8. Status verdict ─────────────────────────────────────────────────────
    if current_day in actual:
        remaining = actual[current_day]
        ideal_remaining = ideal(current_day)
        days_left = total_days - current_day
        # project finish assuming same daily velocity
        completed_so_far = scope[current_day] - remaining
        daily_vel = completed_so_far / current_day if current_day > 0 else 0
        proj_days = math.ceil(remaining / daily_vel) if daily_vel > 0 else 999
        proj_finish_day = current_day + proj_days

        if remaining <= 0:
            verdict = _col(_BOLD + _GREEN, "✔ Sprint complete — all points burned down.")
        elif proj_finish_day <= total_days:
            verdict = _col(_BOLD + _GREEN,
                f"✔ On track — projected finish Day {proj_finish_day} "
                f"({days_left} day{'s' if days_left != 1 else ''} left, "
                f"{remaining:.0f} pts remaining).")
        else:
            overrun = proj_finish_day - total_days
            verdict = _col(_BOLD + _RED,
                f"⚠ At risk — projected finish Day {proj_finish_day} "
                f"({overrun} day{'s' if overrun != 1 else ''} over, "
                f"{remaining:.0f} pts remaining).")

        lines.append(f"  {verdict}")
        lines.append(
            f"  {_col(_DIM, f'Velocity: {daily_vel:.1f} pts/day  |  '
                           f'Ideal remaining: {ideal_remaining:.1f} pts  |  '
                           f'Actual remaining: {remaining:.1f} pts')}"
        )

    return "\n".join(lines)


# ── Processor ─────────────────────────────────────────────────────────────────

class BurndownProcessor(BaseProcessor):
    """Renders a terminal burndown chart from sprint data in the event payload."""

    async def process(self, event: AgentEvent) -> ProcessorResult:
        if event.type != EventType.TRIGGER_BURNDOWN:
            return ProcessorResult()

        data: dict[str, Any] = event.payload.get("burndown_data", {})
        snapshot: dict[str, Any] = event.payload.get("snapshot", {})

        if not data and not snapshot:
            return ProcessorResult()

        sprint_id = event.sprint_id or data.get("sprint_id", "?")
        sprint_name = snapshot.get("sprint_name") or sprint_id
        total_days: int = int(data.get("total_days") or snapshot.get("sprint_total_days") or 8)
        committed_points: float = float(
            data.get("committed_points") or snapshot.get("committed_points") or 0
        )
        scope_changes: list[dict[str, Any]] = data.get("scope_changes", [])
        daily_completed: list[dict[str, Any]] = data.get("daily_completed", [])
        current_day: int = int(snapshot.get("sprint_day") or data.get("current_day") or total_days)

        chart = build_burndown_chart(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            total_days=total_days,
            committed_points=committed_points,
            scope_changes=scope_changes,
            daily_completed=daily_completed,
            current_day=current_day,
        )

        return ProcessorResult(
            enrichments={
                "burndown_sprint_id": sprint_id,
                "burndown_current_day": current_day,
                "burndown_total_days": total_days,
            },
            side_effects=[
                {
                    "action": "burndown_chart",
                    "channel": "console",
                    "sprint_id": sprint_id,
                    "message": chart,
                }
            ],
        )
