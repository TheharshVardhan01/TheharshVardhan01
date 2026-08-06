#!/usr/bin/env python3
"""Convert the prepped grayscale photo into a self-typing ASCII SVG.

Reads source-prepped.png (made by prep_photo.py), downsamples it to a
character grid, and maps brightness to a glyph density ramp. Each row is
wrapped in a horizontal clip that wipes left-to-right with a block cursor
riding the edge, staggered top to bottom, so the portrait "types" itself in.
The animation is SMIL, plays once, and freezes — GitHub renders it inside
an <img> with no JavaScript.

    python scripts/make_ascii_svg.py            # writes avi-ascii.svg
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""

from __future__ import annotations

import html
import os
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

# --- look ------------------------------------------------------------------
INK = "#c9d1d9"        # one light-gray fill — monochrome on purpose
CURSOR = "#39d353"
FONT_SIZE = 11

# --- timing ----------------------------------------------------------------
ROW_WIPE_S = 0.55      # each row's left-to-right wipe duration
ROW_STAGGER_S = 0.055  # delay between successive rows starting
STATIC = os.environ.get("STATIC") == "1"


def load_grid() -> np.ndarray:
    """Downsample the prepped image to a COLS-wide grid of 0-255 values."""
    img = Image.open(SOURCE).convert("L")
    rows = max(1, round(COLS * (img.height / img.width) * ASPECT))
    img = img.resize((COLS, rows), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8)


def to_lines(grid: np.ndarray) -> list[str]:
    """Map each pixel's brightness to a ramp glyph; trim blank right edges."""
    idx = (grid.astype(np.float32) / 255.0 * (len(RAMP) - 1)).round().astype(int)
    # brightness 255 -> index 0 (space), darkest -> densest glyph
    lines = ["".join(RAMP[len(RAMP) - 1 - v] for v in row) for row in idx]
    return [ln.rstrip() for ln in lines]


def build_svg(lines: list[str]) -> str:
    n = len(lines)
    width = round(COLS * CHAR_W)
    height = round(n * CHAR_H + CHAR_H)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="ASCII art portrait that types itself in">'
    )
    parts.append(
        "<style>text{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;"
        f"font-size:{FONT_SIZE}px;fill:{INK};white-space:pre;}}</style>"
    )
    # Transparent background: inherits GitHub's light or dark page color.

    for i, line in enumerate(lines):
        if not line:
            continue
        y = round((i + 1) * CHAR_H, 2)
        begin = round(i * ROW_STAGGER_S, 3)
        dur = ROW_WIPE_S
        clip_id = f"r{i}"

        if STATIC:
            parts.append(
                f'<text x="0" y="{y}" textLength="{round(len(line) * CHAR_W, 2)}" '
                f'lengthAdjust="spacingAndGlyphs">{html.escape(line)}</text>'
            )
            continue

        line_w = round(len(line) * CHAR_W, 2)
        # The clip rect grows 0 -> line width, revealing glyphs already in place:
        # a left-to-right wipe rather than characters sliding around.
        parts.append(f'<clipPath id="{clip_id}"><rect x="0" y="{round(y - CHAR_H, 2)}" '
                     f'width="0" height="{CHAR_H + 2}">'
                     f'<animate attributeName="width" from="0" to="{line_w}" '
                     f'begin="{begin}s" dur="{dur}s" fill="freeze" '
                     f'calcMode="linear"/></rect></clipPath>')
        parts.append(
            f'<g clip-path="url(#{clip_id})">'
            f'<text x="0" y="{y}" textLength="{line_w}" '
            f'lengthAdjust="spacingAndGlyphs">{html.escape(line)}</text></g>'
        )
        # Block cursor riding the wipe edge, hidden once its row is done.
        parts.append(
            f'<rect x="0" y="{round(y - FONT_SIZE, 2)}" width="{CHAR_W}" '
            f'height="{FONT_SIZE + 2}" fill="{CURSOR}" opacity="0">'
            f'<animate attributeName="x" from="0" to="{line_w}" '
            f'begin="{begin}s" dur="{dur}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0.85;0.85;0" '
            f'keyTimes="0;0.05;0.9;1" begin="{begin}s" dur="{dur + 0.15}s" '
            f'fill="freeze"/></rect>'
        )

    parts.append("</svg>")
    return "".join(parts)


def main() -> int:
    if not SOURCE.exists():
        print(f"error: {SOURCE.name} not found — run prep_photo.py first")
        return 1
    lines = to_lines(load_grid())
    svg = build_svg(lines)
    OUT.write_text(svg, encoding="utf-8")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.name} ({mode}, {len(lines)} rows, {len(svg) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
