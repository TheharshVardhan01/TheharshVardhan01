#!/usr/bin/env python3
"""Render data/contributions.json as an animated contribution heatmap SVG.

The classic 53-week x 7-day calendar of rounded, colored boxes with a
GitHub-ish green ramp. The grid reveals itself once with a diagonal,
line-after-line slide-down (CSS keyframes that play on load, then freeze —
no looping glow), plus month labels, a Less->More legend, and a stats footer.

    python scripts/render_heatmap_svg.py        # writes contrib-heatmap.svg
    STATIC=1 python scripts/render_heatmap_svg.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

STATIC = os.environ.get("STATIC") == "1"

# none -> brightest (level 5 is a neon top end used for the best day)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

BG = "#0d1117"
BORDER = "#30363d"
TEXT = "#8b949e"
BRIGHT = "#c9d1d9"
FONT = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

CELL = 13            # box size
GAP = 3              # gutter between boxes
RADIUS = 3
LEFT = 46            # room for day labels
TOP = 42             # room for month labels
PAD = 14

WAVE_S = 1.6         # total time for the diagonal to cross the grid
CELL_IN_S = 0.45     # each box's own slide-in duration

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load() -> dict:
    if not DATA.exists():
        print("error: data/contributions.json not found — "
              "run fetch_contributions.py first", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(DATA.read_text(encoding="utf-8"))


def to_weeks(days: list[dict]) -> list[list[dict | None]]:
    """Bucket days into GitHub's column-per-week, Sunday-first layout."""
    weeks: list[list[dict | None]] = []
    col: list[dict | None] = []
    first_dow = dt.date.fromisoformat(days[0]["date"]).isoweekday() % 7  # Sun=0
    col.extend([None] * first_dow)
    for d in days:
        col.append(d)
        if len(col) == 7:
            weeks.append(col)
            col = []
    if col:
        col.extend([None] * (7 - len(col)))
        weeks.append(col)
    return weeks


def main() -> int:
    payload = load()
    days = payload["days"]
    stats = payload["stats"]
    weeks = to_weeks(days)
    n_weeks = len(weeks)

    best_date = (stats.get("best_day") or {}).get("date")

    grid_w = n_weeks * (CELL + GAP) - GAP
    grid_h = 7 * (CELL + GAP) - GAP
    legend_h = 40
    width = LEFT + grid_w + PAD * 2
    height = TOP + grid_h + legend_h + PAD

    p: list[str] = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="{stats["total"]} contributions in the last year">')

    anim_css = "" if STATIC else (
        ".c{opacity:0;animation:in %ss cubic-bezier(.2,.7,.3,1) forwards;}"
        "@keyframes in{from{opacity:0;transform:translateY(-14px);}"
        "to{opacity:1;transform:translateY(0);}}"
        ".f{opacity:0;animation:fade .6s ease-out forwards;animation-delay:%ss;}"
        "@keyframes fade{to{opacity:1;}}"
    ) % (CELL_IN_S, round(WAVE_S + 0.3, 2))
    static_css = ".c{opacity:1;}.f{opacity:1;}" if STATIC else ""
    p.append(f"<style>text{{font-family:{FONT};font-size:11px;fill:{TEXT};}}"
             f"{anim_css}{static_css}</style>")

    p.append(f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
             f'rx="8" fill="{BG}" stroke="{BORDER}"/>')

    # month labels along the top (label the first week of each new month)
    seen_month = None
    for x_i, week in enumerate(weeks):
        first = next((d for d in week if d), None)
        if not first:
            continue
        month = first["date"][:7]
        if month != seen_month:
            seen_month = month
            mx = LEFT + x_i * (CELL + GAP)
            if mx + 28 < width - PAD:  # don't let the last label overflow
                m_idx = int(month[5:7]) - 1
                p.append(f'<text class="f" x="{mx}" y="{TOP - 12}">{MONTHS[m_idx]}</text>')

    # day labels
    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        ly = TOP + row * (CELL + GAP) + CELL - 3
        p.append(f'<text class="f" x="{PAD}" y="{ly}">{label}</text>')

    # the grid — diagonal wave: delay grows with column + row
    for x_i, week in enumerate(weeks):
        for y_i, day in enumerate(week):
            if day is None:
                continue
            x = LEFT + x_i * (CELL + GAP)
            y = TOP + y_i * (CELL + GAP)
            level = min(day["level"], 4)
            # the single best day gets the neon top end of the ramp
            color = PALETTE[5] if (best_date and day["date"] == best_date
                                   and day["count"] > 0) else PALETTE[level]
            delay = round((x_i + y_i) / (n_weeks + 7) * WAVE_S, 3)
            style = "" if STATIC else f' style="animation-delay:{delay}s"'
            p.append(f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                     f'rx="{RADIUS}" fill="{color}"{style}>'
                     f'<title>{day["count"]} on {day["date"]}</title></rect>')

    # footer: stats left, legend right
    fy = TOP + grid_h + 26
    total = f"{stats['total']:,}"
    p.append(f'<text class="f" x="{LEFT}" y="{fy}">'
             f'<tspan fill="{BRIGHT}">{total}</tspan> contributions in the last year'
             f'<tspan dx="14" fill="{TEXT}">·</tspan>'
             f'<tspan dx="14">streak </tspan><tspan fill="{BRIGHT}">'
             f'{stats["current_streak"]}d</tspan>'
             f'<tspan dx="14" fill="{TEXT}">·</tspan>'
             f'<tspan dx="14">longest </tspan><tspan fill="{BRIGHT}">'
             f'{stats["longest_streak"]}d</tspan></text>')

    lx = width - PAD - 5 * (CELL + GAP) - 76
    p.append(f'<text class="f" x="{lx - 34}" y="{fy}">Less</text>')
    for i in range(5):
        p.append(f'<rect class="f" x="{lx + i * (CELL + GAP)}" y="{fy - CELL + 3}" '
                 f'width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{PALETTE[i]}"/>')
    p.append(f'<text class="f" x="{lx + 5 * (CELL + GAP) + 6}" y="{fy}">More</text>')

    p.append("</svg>")
    OUT.write_text("".join(p), encoding="utf-8")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.name} ({mode}, {n_weeks} weeks, {width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
