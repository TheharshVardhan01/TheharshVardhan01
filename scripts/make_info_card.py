#!/usr/bin/env python3
"""Hand-author a neofetch-style info card SVG.

A title bar plus colored key/value rows, like the output of the `neofetch`
command. Each line fades and slides in on a short stagger so the panel looks
like it's printing next to the ASCII portrait. Animation is pure SMIL: plays
once on load, then freezes.

    python scripts/make_info_card.py            # writes info-card.svg
    STATIC=1 python scripts/make_info_card.py   # frozen frame for previews

Edit ROWS below when your details change, then re-run and commit.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "info-card.svg"

STATIC = os.environ.get("STATIC") == "1"

# --- content ---------------------------------------------------------------
TITLE = "harsh@github"
HOST_LINE = "harsh@github"
SEP = "-" * len(HOST_LINE)

# (key, value) rows; key of "" prints the value as a plain line.
ROWS: list[tuple[str, str]] = [
    ("OS", "AI/ML Engineering (B.Tech @ GSV)"),
    ("Kernel", "agentic-systems 5.x"),
    ("Shell", "python + pytorch"),
    ("Now", "multi-agent architectures, LLM eval & benchmarking"),
    ("Focus", "agentic systems · computer vision · MLOps"),
    ("Stack", "PyTorch · LangChain · OpenCV · FastAPI · Docker"),
    ("Projects", "RAGvisor · DeepDetect · AI Krishidoot"),
    ("", ""),
    ("Web", "theharshvardhan01.github.io"),
    ("Contact", "harsh.vardhan_btech23@gsv.ac.in"),
]

# --- look ------------------------------------------------------------------
BG = "#0d1117"
BORDER = "#30363d"
KEY = "#58a6ff"      # neofetch keys read in accent blue
VAL = "#c9d1d9"
DIM = "#8b949e"
GREEN = "#39d353"

FONT = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
FS = 12.5            # font size
LH = 21              # line height
PAD_X = 22
TITLEBAR_H = 34

STAGGER = 0.16       # delay between rows appearing
FADE = 0.35          # each row's fade/slide duration
T0 = 0.3             # pause before the first row


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def appear(begin: float) -> str:
    """Fade + small upward slide, then freeze. Empty string in static mode."""
    if STATIC:
        return ""
    return (
        f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" '
        f'dur="{FADE}s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" '
        f'from="0 6" to="0 0" begin="{begin:.2f}s" dur="{FADE}s" fill="freeze"/>'
    )


def main() -> int:
    # host line + separator + rows + swatch strip
    n_lines = 2 + len(ROWS) + 2
    width = 490
    height = TITLEBAR_H + 18 + n_lines * LH + 14

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(TITLE)} info card">'
    )
    p.append(f"<style>text{{font-family:{FONT};font-size:{FS}px;}}</style>")

    # panel + title bar
    p.append(f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
             f'rx="8" fill="{BG}" stroke="{BORDER}"/>')
    p.append(f'<path d="M0.5 {TITLEBAR_H} H{width - 0.5}" stroke="{BORDER}"/>')
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        p.append(f'<circle cx="{20 + i * 20}" cy="{TITLEBAR_H / 2}" r="5.5" fill="{c}"/>')
    p.append(f'<text x="{width / 2}" y="{TITLEBAR_H / 2 + 4.5}" text-anchor="middle" '
             f'fill="{DIM}">{esc(TITLE)}</text>')

    y = TITLEBAR_H + 18 + LH * 0.6
    begin = T0

    def line(inner: str, dy: float = 0) -> None:
        nonlocal y, begin
        op = "1" if STATIC else "0"
        p.append(f'<g opacity="{op}">{appear(begin)}{inner}</g>')
        y += LH + dy
        begin += STAGGER

    # host + separator, like neofetch's header
    line(f'<text x="{PAD_X}" y="{y}"><tspan fill="{GREEN}">{esc(HOST_LINE)}</tspan></text>')
    line(f'<text x="{PAD_X}" y="{y}" fill="{DIM}">{esc(SEP)}</text>')

    for key, val in ROWS:
        if not key and not val:
            y += LH * 0.35   # blank spacer row, no animation slot burned
            continue
        if key:
            inner = (f'<text x="{PAD_X}" y="{y}">'
                     f'<tspan fill="{KEY}">{esc(key)}</tspan>'
                     f'<tspan fill="{DIM}">: </tspan>'
                     f'<tspan fill="{VAL}">{esc(val)}</tspan></text>')
        else:
            inner = f'<text x="{PAD_X}" y="{y}" fill="{VAL}">{esc(val)}</text>'
        line(inner)

    # neofetch's trailing color swatches
    y += LH * 0.2
    sw, sh = 26, 13
    colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
    swatches = "".join(
        f'<rect x="{PAD_X + i * sw}" y="{y - sh + 2}" width="{sw}" height="{sh}" '
        f'fill="{c}"/>' for i, c in enumerate(colors)
    )
    op = "1" if STATIC else "0"
    p.append(f'<g opacity="{op}">{appear(begin)}{swatches}</g>')

    p.append("</svg>")
    OUT.write_text("".join(p), encoding="utf-8")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.name} ({mode}, {len(ROWS)} rows, {height}px tall)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
