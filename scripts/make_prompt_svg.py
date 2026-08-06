#!/usr/bin/env python3
"""Animated section headers: a shell prompt that types its command, then a
block cursor blinks forever. One SVG per README section.

    python scripts/make_prompt_svg.py            # writes prompt-*.svg
    STATIC=1 python scripts/make_prompt_svg.py   # frozen frames
"""

from __future__ import annotations

import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"

PROMPT = "harsh@github ~ $ "
CMDS = {
    "prompt-contrib.svg": "./contributions.sh",
    "prompt-whoami.svg": "whoami",
    "prompt-projects.svg": "ls ~/projects",
    "prompt-contact.svg": "cat ~/.contact",
}

FONT = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
FS = 14
CH = 8.4               # monospace advance at FS
H = 34
PAD = 10
BASE = 23              # text baseline

PROMPT_COLOR = "#39d353"
CMD_COLOR = "#c9d1d9"
CURSOR = "#7ee787"
TYPE_CPS = 16          # typed characters per second


def build(cmd: str) -> str:
    prompt_w = round(len(PROMPT) * CH, 2)
    cmd_w = round(len(cmd) * CH, 2)
    width = round(PAD * 2 + prompt_w + cmd_w + CH + 4)
    type_s = round(len(cmd) / TYPE_CPS, 2)

    x0 = PAD + prompt_w                    # where the command starts
    x1 = round(x0 + cmd_w, 2)              # where the cursor rests

    p: list[str] = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" '
             f'viewBox="0 0 {width} {H}" role="img" '
             f'aria-label="{html.escape(PROMPT + cmd)}">')
    p.append(f"<style>text{{font-family:{FONT};font-size:{FS}px;white-space:pre;}}</style>")

    p.append(f'<text x="{PAD}" y="{BASE}" fill="{PROMPT_COLOR}" '
             f'textLength="{prompt_w}" lengthAdjust="spacingAndGlyphs">'
             f'{html.escape(PROMPT.rstrip())} </text>')

    if STATIC:
        p.append(f'<text x="{x0}" y="{BASE}" fill="{CMD_COLOR}" '
                 f'textLength="{cmd_w}" lengthAdjust="spacingAndGlyphs">'
                 f'{html.escape(cmd)}</text>')
        p.append(f'<rect x="{x1 + 3}" y="{BASE - FS + 2}" width="{CH}" height="{FS}" '
                 f'fill="{CURSOR}"/>')
    else:
        # command wipes in left-to-right
        p.append(f'<clipPath id="c"><rect x="{x0}" y="0" width="0" height="{H}">'
                 f'<animate attributeName="width" from="0" to="{cmd_w}" '
                 f'begin="0.4s" dur="{type_s}s" fill="freeze" calcMode="linear"/>'
                 f'</rect></clipPath>')
        p.append(f'<g clip-path="url(#c)"><text x="{x0}" y="{BASE}" fill="{CMD_COLOR}" '
                 f'textLength="{cmd_w}" lengthAdjust="spacingAndGlyphs">'
                 f'{html.escape(cmd)}</text></g>')
        # cursor rides the wipe, then blinks at the end forever
        p.append(f'<rect x="{x0}" y="{BASE - FS + 2}" width="{CH}" height="{FS}" '
                 f'fill="{CURSOR}">'
                 f'<animate attributeName="x" from="{x0}" to="{x1 + 3}" '
                 f'begin="0.4s" dur="{type_s}s" fill="freeze" calcMode="linear"/>'
                 f'<animate attributeName="opacity" values="1;1;0;0" '
                 f'keyTimes="0;0.5;0.5;1" begin="{round(0.4 + type_s, 2)}s" dur="1.1s" '
                 f'repeatCount="indefinite"/></rect>')

    p.append("</svg>")
    return "".join(p)


def main() -> int:
    for name, cmd in CMDS.items():
        (ROOT / name).write_text(build(cmd), encoding="utf-8")
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
