#!/usr/bin/env python3
"""Fetch the public contribution calendar — no token, no GraphQL.

GitHub serves the contribution calendar as public HTML at
https://github.com/users/<username>/contributions — the same fragment the
profile page itself embeds. We fetch it with requests, parse the day cells
with BeautifulSoup, and write data/contributions.json with the raw days plus
derived stats (total, streaks, best day, monthly totals).

    python scripts/fetch_contributions.py
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = "TheharshVardhan01"
URL = f"https://github.com/users/{USERNAME}/contributions"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"

# Tooltip text like "3 contributions on August 5th." / "No contributions on ..."
COUNT_RE = re.compile(r"^(No|\d[\d,]*)\s+contribution", re.IGNORECASE)


def fetch_html() -> str:
    resp = requests.get(
        URL,
        headers={"User-Agent": "profile-readme-heatmap (+github.com/TheharshVardhan01)"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def parse_days(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")

    # Map cell id -> tooltip text; the count lives in <tool-tip for="...">.
    tips: dict[str, str] = {
        tip.get("for"): tip.get_text(strip=True)
        for tip in soup.find_all("tool-tip")
        if tip.get("for")
    }

    days = []
    for td in soup.select("td.ContributionCalendar-day[data-date]"):
        date = td["data-date"]
        level = int(td.get("data-level", 0))
        count = 0
        tip = tips.get(td.get("id", ""), "")
        m = COUNT_RE.match(tip)
        if m and m.group(1).lower() != "no":
            count = int(m.group(1).replace(",", ""))
        days.append({"date": date, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])
    return days


def derive_stats(days: list[dict]) -> dict:
    total = sum(d["count"] for d in days)

    best = max(days, key=lambda d: d["count"], default=None)

    # Streaks over the calendar window. The current streak may legitimately
    # be broken by "today has no contributions yet", so allow the last day
    # to be zero without ending it.
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["count"] > 0 else 0
        longest = max(longest, cur)

    current = 0
    for i, d in enumerate(reversed(days)):
        if d["count"] > 0:
            current += 1
        elif i == 0:
            continue          # today, nothing pushed yet — streak still alive
        else:
            break

    monthly: dict[str, int] = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]

    return {
        "total": total,
        "best_day": best,
        "current_streak": current,
        "longest_streak": longest,
        "monthly": monthly,
    }


def main() -> int:
    print(f"fetching {URL}")
    days = parse_days(fetch_html())
    if not days:
        print("error: no day cells parsed — GitHub may have changed the markup",
              file=sys.stderr)
        return 1

    stats = derive_stats(days)
    payload = {
        "username": USERNAME,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "stats": stats,
        "days": days,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(days)} days, "
          f"{stats['total']} contributions, "
          f"streak {stats['current_streak']} (longest {stats['longest_streak']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
