#!/usr/bin/env python3
"""Rank the next thing to build, per RUBRIC.md.

Deterministic on purpose: the rubric decides, not the mood of the run.

Usage:
    python3 tools/select.py                 # today's default lane, top 3
    python3 tools/select.py --lane build    # force the build lane
    python3 tools/select.py --lane harden   # force the hardening lane
    python3 tools/select.py --json          # machine readable
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"

WEIGHTS = {"s1": 0.25, "s2": 0.20, "s3": 0.15, "s4": 0.15, "s5": 0.10, "s6": 0.05, "s7": 0.10}

STOPWORDS = {
    "a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "that", "this", "is",
    "are", "it", "as", "at", "by", "or", "not", "you", "your", "their", "they", "them",
    "from", "into", "than", "then", "when", "what", "who", "how", "why", "be", "been",
    "can", "cannot", "does", "do", "did", "has", "have", "had", "will", "would", "should",
    "one", "two", "three", "all", "any", "more", "most", "some", "no", "own", "same",
    "its", "if", "but", "so", "up", "out", "about", "over", "under", "again", "here",
    "there", "where", "which", "while", "after", "before", "because", "between", "each",
}

THEMES_BY_WEEKDAY = {
    0: "build",     # Monday
    1: "harden",    # Tuesday
    2: "build",     # Wednesday
    3: "harden",    # Thursday
    4: "build",     # Friday
    5: "harden",    # Saturday
    6: "recap",     # Sunday
}


def load(name: str) -> dict:
    return json.loads((STATE / name).read_text())


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def base_score(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 3)


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def build_candidates(ledger: dict, today: str) -> list[dict]:
    backlog = load("backlog.json")["items"]
    shipped = ledger.get("shipped", [])
    recent = shipped[-10:]
    recent_tokens = [tokens(f"{s.get('title', '')} {s.get('thesis', '')}") for s in recent]

    last5_themes = [s.get("theme", "") for s in shipped[-5:]]
    month = today[:7]
    month_themes = [s.get("theme", "") for s in shipped if s.get("date", "").startswith(month)]

    out = []
    for item in backlog:
        if item["status"] not in {"queued", "proposed"}:
            continue
        score = base_score(item["scores"])
        penalties = []
        item_tokens = tokens(f"{item['title']} {item['thesis']}")
        worst_overlap = max((overlap(item_tokens, rt) for rt in recent_tokens), default=0.0)
        if worst_overlap > 0.40:
            score -= 0.5
            penalties.append(f"overlap {worst_overlap:.2f} with a recent ship")
        if item["theme"] in last5_themes:
            score -= 1.0
            penalties.append(f"theme '{item['theme']}' shipped in the last 5 days")
        if month_themes.count(item["theme"]) >= 2:
            score = 0.0
            penalties.append(f"theme '{item['theme']}' already hit its monthly ceiling")
        out.append({
            "id": item["id"],
            "title": item["title"],
            "thesis": item["thesis"],
            "theme": item["theme"],
            "base": round(base_score(item["scores"]), 3),
            "score": round(score, 3),
            "penalties": penalties,
            "notes": item.get("notes", ""),
        })
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out


def harden_candidates() -> list[dict]:
    items = load("hardening.json")["items"]
    out = []
    for item in items:
        if item["status"] not in {"queued", "proposed"}:
            continue
        priority = round(item["impact"] * item["confidence"] / item["effort"], 2)
        out.append({**item, "priority": priority})
    out.sort(key=lambda x: (-x["priority"], x["id"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=["build", "harden", "recap", "auto"], default="auto")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ledger = load("ledger.json")
    lane = THEMES_BY_WEEKDAY[date.fromisoformat(args.date).weekday()] if args.lane == "auto" else args.lane

    payload = {"date": args.date, "lane": lane}
    if lane == "build":
        payload["candidates"] = build_candidates(ledger, args.date)[: args.top]
        payload["threshold"] = 3.6
    elif lane == "recap":
        payload["shipped"] = ledger.get("shipped", [])
        payload["note"] = "Sunday lane: recap, promote any artifact at 4.2 or above, refresh dashboard, draft the weekly post."
    else:
        payload["candidates"] = harden_candidates()[: args.top]
        payload["threshold"] = 4.0

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"date: {payload['date']}  lane: {lane}")
    if lane == "recap":
        print(payload["note"])
        return
    print(f"ship threshold: {payload['threshold']}\n")
    for i, c in enumerate(payload["candidates"], 1):
        label = c.get("priority", c.get("score"))
        print(f"{i}. [{label}] {c['title']}  ({c['id']})")
        if c.get("thesis"):
            print(f"   {c['thesis']}")
        if c.get("defect"):
            print(f"   defect: {c['defect']}")
        if c.get("penalties"):
            print(f"   penalties: {'; '.join(c['penalties'])}")
        if c.get("notes"):
            print(f"   note: {c['notes']}")
        print()


if __name__ == "__main__":
    main()
