#!/usr/bin/env python3
"""Convert the prepped grayscale photo into a living, matrix-green ASCII SVG.

Reads source-prepped.png (made by prep_photo.py), downsamples it to a
character grid, and maps brightness to a glyph density ramp. Darker areas of
the photo print denser glyphs in brighter green, so the subject glows out of
the dark background like a phosphor terminal.

The portrait types itself in row by row (a glowing block cursor rides each
wipe), and then — unlike a type-once-and-freeze SVG — it stays alive forever:

  * a scanline sweeps down the portrait on an infinite loop
  * random glyphs flicker bright like a CRT refreshing
  * everything is SMIL inside the SVG, so GitHub plays it in an <img>

    python scripts/make_ascii_svg.py            # writes ascii-portrait.svg
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""

from __future__ import annotations

import html
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"

# --- character grid --------------------------------------------------------
COLS = 100
CHAR_W = 7.2          # px per character cell (monospace advance)
CHAR_H = 13.0         # px per row (line height)
# A terminal cell is taller than wide, so vertical sampling must compensate
# or the face comes out stretched.
ASPECT = CHAR_W / CHAR_H

# bright (sparse) -> dark (dense); the leading space clears the background
RAMP = " .`:-=+*cs#%@"

# --- look: matrix green ----------------------------------------------------
# Density tier -> green. Sparse glyphs sit dim in the background; dense
# glyphs (the subject) burn neon. GitHub's own contribution ramp, extended.
TIER_COLORS = ["#0e4429", "#1a7f37", "#26a641", "#39d353", "#7ee787"]
CURSOR = "#7ee787"
FLICKER = "#b7ffd0"
FONT_SIZE = 11

# --- timing ----------------------------------------------------------------
ROW_WIPE_S = 0.55      # each row's left-to-right wipe duration
ROW_STAGGER_S = 0.055  # delay between successive rows starting
SCAN_PERIOD_S = 5.5    # scanline loop duration
N_FLICKERS = 70        # glyphs that keep flickering after the type-in
STATIC = os.environ.get("STATIC") == "1"

random.seed(1729)      # deterministic flicker layout run-to-run


def load_grid() -> np.ndarray:
    """Downsample the prepped image to a COLS-wide grid of 0-255 values."""
    img = Image.open(SOURCE).convert("L")
    rows = max(1, round(COLS * (img.height / img.width) * ASPECT))
    img = img.resize((COLS, rows), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8)


def to_indices(grid: np.ndarray) -> np.ndarray:
    """Map brightness to ramp indices: 0 = space, len(RAMP)-1 = densest."""
    idx = (grid.astype(np.float32) / 255.0 * (len(RAMP) - 1)).round().astype(int)
    return (len(RAMP) - 1) - idx   # brightness 255 -> 0 (space)


def tier_of(ramp_idx: int) -> int:
    """Quantize a nonzero ramp index into a color tier."""
    t = (ramp_idx - 1) / max(len(RAMP) - 2, 1)
    return min(len(TIER_COLORS) - 1, round(t * (len(TIER_COLORS) - 1)))


def row_tspans(row: np.ndarray, y: float) -> tuple[str, float]:
    """One row as color-tiered tspan runs; returns (markup, right edge px)."""
    spans: list[str] = []
    right = 0.0
    col = 0
    n = len(row)
    while col < n:
        idx = int(row[col])
        if idx == 0:
            col += 1
            continue
        tier = tier_of(idx)
        start = col
        chars: list[str] = []
        # extend the run while the tier stays the same (spaces end a run)
        while col < n and int(row[col]) != 0 and tier_of(int(row[col])) == tier:
            chars.append(RAMP[int(row[col])])
            col += 1
        run_w = round(len(chars) * CHAR_W, 2)
        x = round(start * CHAR_W, 2)
        spans.append(
            f'<tspan x="{x}" y="{y}" textLength="{run_w}" '
            f'lengthAdjust="spacingAndGlyphs" fill="{TIER_COLORS[tier]}">'
            f'{html.escape("".join(chars))}</tspan>'
        )
        right = x + run_w
    return "".join(spans), right


def build_svg(idx: np.ndarray) -> str:
    n_rows = len(idx)
    width = round(COLS * CHAR_W)
    height = round(n_rows * CHAR_H + CHAR_H)
    type_in_end = round(n_rows * ROW_STAGGER_S + ROW_WIPE_S, 2)
    loops_begin = round(type_in_end + 0.6, 2)

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Matrix-green ASCII art portrait that types itself in and stays animated">'
    )
    p.append(
        "<style>text{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;"
        f"font-size:{FONT_SIZE}px;white-space:pre;}}</style>"
    )
    p.append(
        '<defs>'
        '<filter id="glow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="1.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#39d353" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="#39d353" stop-opacity="0.22"/>'
        '<stop offset="1" stop-color="#39d353" stop-opacity="0"/>'
        '</linearGradient>'
        '</defs>'
    )
    # Transparent background: inherits GitHub's light or dark page color.

    # --- the glyph rows, typed in row by row -------------------------------
    flicker_pool: list[tuple[float, float, str]] = []   # (x, y, char)
    for i in range(n_rows):
        y = round((i + 1) * CHAR_H, 2)
        spans, right = row_tspans(idx[i], y)
        if not spans:
            continue

        # remember bright glyphs as flicker candidates
        for col in range(COLS):
            v = int(idx[i][col])
            if v and tier_of(v) >= 3:
                flicker_pool.append((round(col * CHAR_W, 2), y, RAMP[v]))

        if STATIC:
            p.append(f"<text>{spans}</text>")
            continue

        begin = round(i * ROW_STAGGER_S, 3)
        clip_id = f"r{i}"
        # The clip rect grows 0 -> row width, revealing glyphs already in
        # place: a left-to-right wipe rather than characters sliding around.
        p.append(f'<clipPath id="{clip_id}"><rect x="0" y="{round(y - CHAR_H, 2)}" '
                 f'width="0" height="{CHAR_H + 2}">'
                 f'<animate attributeName="width" from="0" to="{right}" '
                 f'begin="{begin}s" dur="{ROW_WIPE_S}s" fill="freeze" '
                 f'calcMode="linear"/></rect></clipPath>')
        p.append(f'<g clip-path="url(#{clip_id})"><text>{spans}</text></g>')
        # Glowing block cursor riding the wipe edge, hidden once its row is done.
        p.append(
            f'<rect x="0" y="{round(y - FONT_SIZE, 2)}" width="{CHAR_W}" '
            f'height="{FONT_SIZE + 2}" fill="{CURSOR}" opacity="0" filter="url(#glow)">'
            f'<animate attributeName="x" from="0" to="{right}" '
            f'begin="{begin}s" dur="{ROW_WIPE_S}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0.9;0.9;0" '
            f'keyTimes="0;0.05;0.9;1" begin="{begin}s" dur="{ROW_WIPE_S + 0.15}s" '
            f'fill="freeze"/></rect>'
        )

    if not STATIC:
        # --- infinite scanline sweep ---------------------------------------
        p.append(
            f'<rect x="0" y="0" width="{width}" height="30" fill="url(#scan)" '
            f'opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{loops_begin}s" dur="0.4s" fill="freeze"/>'
            f'<animate attributeName="y" from="-32" to="{height}" '
            f'begin="{loops_begin}s" dur="{SCAN_PERIOD_S}s" '
            f'repeatCount="indefinite" calcMode="linear"/></rect>'
        )
        # --- CRT glyph flicker, forever ------------------------------------
        chosen = random.sample(flicker_pool, min(N_FLICKERS, len(flicker_pool)))
        for x, y, ch in chosen:
            delay = round(loops_begin + random.uniform(0, 6.0), 2)
            period = round(random.uniform(2.2, 6.5), 2)
            p.append(
                f'<text x="{x}" y="{y}" fill="{FLICKER}" opacity="0" '
                f'filter="url(#glow)" textLength="{CHAR_W}" '
                f'lengthAdjust="spacingAndGlyphs">{html.escape(ch)}'
                f'<animate attributeName="opacity" values="0;1;0;0" '
                f'keyTimes="0;0.05;0.14;1" begin="{delay}s" dur="{period}s" '
                f'repeatCount="indefinite"/></text>'
            )

    p.append("</svg>")
    return "".join(p)


def main() -> int:
    if not SOURCE.exists():
        print(f"error: {SOURCE.name} not found — run prep_photo.py first")
        return 1
    svg = build_svg(to_indices(load_grid()))
    OUT.write_text(svg, encoding="utf-8")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.name} ({mode}, {len(svg) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
