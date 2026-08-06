#!/usr/bin/env python3
"""Matrix-rain name banner: falling green glyph streams on an infinite loop.

Columns of katakana/digits scroll down forever (two stacked copies of each
stream + a translate loop = a seamless wrap), with the name floating on a
dark glass pill above the rain. Pure SMIL — GitHub plays it in an <img>.

    python scripts/make_banner.py            # writes banner.svg
    STATIC=1 python scripts/make_banner.py   # frozen frame for previews
"""

from __future__ import annotations

import html
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "banner.svg"

STATIC = os.environ.get("STATIC") == "1"
random.seed(42)   # deterministic rain layout run-to-run

W, H = 860, 96
NAME = "HARSH VARDHAN"
TAG = "ai/ml engineer · agentic systems · computer vision · mlops"

GLYPHS = "01アイウエオカキクケコサシスセソタチツテトナニヌネノ<>[]{}$#*+=~"
COL_STEP = 18          # px between rain columns
GLYPH_STEP = 13        # px between glyphs in a stream
FONT = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

BG = "#0d1117"
BORDER = "#1b2a1f"
DIMS = ["#0e4429", "#006d32", "#26a641"]   # stream colors, mostly dim
NAME_COLOR = "#7ee787"
TAG_COLOR = "#39d353"


def rain_column(x: int) -> str:
    """One falling stream: two stacked copies + a translate loop."""
    n = (H // GLYPH_STEP) + 4                 # glyphs per copy, overscan a bit
    copy_h = n * GLYPH_STEP
    color = random.choices(DIMS, weights=[5, 3, 1])[0]
    opacity = round(random.uniform(0.16, 0.42), 2)
    dur = round(random.uniform(4.5, 10.0), 2)
    phase = round(random.uniform(0, dur), 2)

    chars = [random.choice(GLYPHS) for _ in range(n)]
    tspans = "".join(
        f'<tspan x="{x}" y="{-copy_h + (i + 1) * GLYPH_STEP}">{html.escape(c)}</tspan>'
        for i, c in enumerate(chars * 2)      # second copy continues below
    )
    anim = "" if STATIC else (
        f'<animateTransform attributeName="transform" type="translate" '
        f'from="0 0" to="0 {copy_h}" begin="-{phase}s" dur="{dur}s" '
        f'repeatCount="indefinite" calcMode="linear"/>'
    )
    return (f'<g opacity="{opacity}">{anim}'
            f'<text fill="{color}">{tspans}</text></g>')


def main() -> int:
    p: list[str] = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(NAME)} — '
             f'{html.escape(TAG)}">')
    p.append(f"<style>text{{font-family:{FONT};font-size:11px;}}</style>")
    p.append(
        '<defs>'
        '<filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
        '<feGaussianBlur stdDeviation="1.6" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        f'<clipPath id="frame"><rect x="0" y="0" width="{W}" height="{H}" rx="8"/></clipPath>'
        '</defs>'
    )
    p.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8" '
             f'fill="{BG}" stroke="{BORDER}"/>')

    p.append('<g clip-path="url(#frame)">')
    for x in range(10, W - 4, COL_STEP):
        if random.random() < 0.12:
            continue                           # leave a few gaps, looks organic
        p.append(rain_column(x))
    p.append('</g>')

    # glass pill + name
    pill_w, pill_h = 520, 62
    px, py = (W - pill_w) / 2, (H - pill_h) / 2
    p.append(f'<rect x="{px}" y="{py}" width="{pill_w}" height="{pill_h}" rx="10" '
             f'fill="{BG}" opacity="0.78"/>')
    p.append(f'<rect x="{px}" y="{py}" width="{pill_w}" height="{pill_h}" rx="10" '
             f'fill="none" stroke="#2ea043" stroke-opacity="0.35"/>')
    breathe = "" if STATIC else (
        '<animate attributeName="opacity" values="0.92;1;0.92" dur="4s" '
        'repeatCount="indefinite"/>'
    )
    p.append(f'<text x="{W / 2}" y="{py + 27}" text-anchor="middle" '
             f'fill="{NAME_COLOR}" filter="url(#glow)" '
             f'style="font-size:20px;font-weight:bold;letter-spacing:6px">'
             f'{html.escape(NAME)}{breathe}</text>')
    p.append(f'<text x="{W / 2}" y="{py + 48}" text-anchor="middle" '
             f'fill="{TAG_COLOR}" style="font-size:11px;letter-spacing:1px">'
             f'{html.escape(TAG)}</text>')

    p.append("</svg>")
    OUT.write_text("".join(p), encoding="utf-8")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.name} ({mode}, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
