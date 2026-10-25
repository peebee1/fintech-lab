#!/usr/bin/env python3
"""Render the dashboard, BACKLOG.md, and HARDENING.md from state/*.json.

Run after every ship. CI fails if the rendered files are out of date, which keeps the
public surface honest.

Usage:
    python3 tools/render_readme.py          # write files
    python3 tools/render_readme.py --check  # exit 1 if anything would change
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
START = "<!-- DASHBOARD:START -->"
END = "<!-- DASHBOARD:END -->"


def load(name: str) -> dict:
    return json.loads((STATE / name).read_text())


WEIGHTS = {"s1": 0.25, "s2": 0.20, "s3": 0.15, "s4": 0.15, "s5": 0.10, "s6": 0.05, "s7": 0.10}


def score_of(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 2)


def streak(shipped: list[dict], today: date) -> tuple[int, int]:
    days = sorted({s["date"] for s in shipped if s.get("date")}, reverse=True)
    if not days:
        return 0, 0

    def run_length(start_index: int) -> int:
        length, cursor = 1, date.fromisoformat(days[start_index])
        for raw in days[start_index + 1:]:
            nxt = date.fromisoformat(raw)
            if (cursor - nxt).days == 1:
                length += 1
                cursor = nxt
            elif nxt != cursor:
                break
        return length

    current = 0
    if days:
        newest = date.fromisoformat(days[0])
        if (today - newest).days <= 1:
            current = run_length(0)
    best = max(run_length(i) for i in range(len(days)))
    return current, best


def dashboard(ledger: dict, today: date) -> str:
    shipped = ledger.get("shipped", [])
    current, best = streak(shipped, today)
    harden = [s for s in shipped if s.get("lane") == "harden"]
    builds = [s for s in shipped if s.get("lane") != "harden"]
    last = shipped[-1] if shipped else None

    def plural(n: int, singular: str, plural_form: str | None = None) -> str:
        return f"{n} {singular}" if n == 1 else f"{n} {plural_form or singular + 's'}"

    lines = []
    lines.append(f"**{plural(len(shipped), 'ship')}** | **{current} day streak** (best {best}) | "
                 f"{plural(len(builds), 'new artifact')} | "
                 f"{plural(len(harden), 'fix', 'fixes')} to existing repos\n")

    if last:
        lines.append(f"Latest: **{last['title']}** ({last['date']})")
        if last.get("thesis"):
            lines.append(f"\n> {last['thesis']}\n")
        link = last.get("url")
        if link:
            label = "Code and results" if last.get("path") else "Commit"
            lines.append(f"[{label}]({link})\n")

    lines.append("## Shipped\n")
    if not shipped:
        lines.append("_Nothing yet. The first artifact lands with the first build run._\n")
    else:
        lines.append("| Date | Artifact | Claim | Tests | Score |")
        lines.append("|---|---|---|---|---|")
        for s in reversed(shipped):
            path = s.get("path", "")
            name = f"[{s['title']}]({path})" if path else s["title"]
            tests = s.get("tests", {})
            tests_txt = f"{tests.get('passed', 0)} passed" if tests else "n/a"
            score = f"{s['score']:.2f}" if s.get("score") else "n/a"
            claim = (s.get("thesis") or "").replace("|", "/")
            lines.append(f"| {s['date']} | {name} | {claim} | {tests_txt} | {score} |")
        lines.append("")

    promoted = [s for s in shipped if s.get("promoted") and s.get("promoted_url")]
    if promoted:
        lines.append("## Promoted\n")
        lines.append("An artifact moves to its own repo when it scores 4.2 or higher, its "
                     "measurements reproduce, and its thesis survives without this lab.\n")
        for s in promoted:
            slug = s["promoted_url"].rstrip("/").rsplit("/", 1)[-1]
            claim = (s.get("thesis") or "").replace("|", "/")
            lines.append(f"- [{slug}]({s['promoted_url']}): {claim}")
        lines.append("")

    return "\n".join(lines)


def render_readme() -> str:
    today = date.today()
    readme_path = ROOT / "README.md"
    text = readme_path.read_text()
    block = f"{START}\n{dashboard(load('ledger.json'), today)}\n{END}"
    if START in text and END in text:
        head = text.split(START)[0]
        tail = text.split(END)[1]
        return f"{head}{block}{tail}"
    return text.rstrip() + "\n\n" + block + "\n"


def render_backlog() -> str:
    items = load("backlog.json")["items"]
    open_items = [i for i in items if i["status"] in {"queued", "proposed"}]
    open_items.sort(key=lambda i: (-score_of(i["scores"]), i["id"]))
    done = [i for i in items if i["status"] not in {"queued", "proposed"}]

    lines = [
        "# Backlog",
        "",
        "Ranked by the rubric, not by enthusiasm. Machine readable source is `state/backlog.json`.",
        "Run `python3 tools/select.py` for the selector's pick, including the anti repetition penalties.",
        "",
        "## Open",
        "",
        "| Score | Item | Theme | Claim |",
        "|---|---|---|---|",
    ]
    for i in open_items:
        lines.append(f"| {score_of(i['scores']):.2f} | {i['title']} | {i['theme']} | {i['thesis']} |")
    lines += ["", "## Closed", "", "| Status | Item | Theme |", "|---|---|---|"]
    for i in done:
        lines.append(f"| {i['status']} | {i['title']} | {i['theme']} |")
    lines.append("")
    return "\n".join(lines)


def render_hardening() -> str:
    items = load("hardening.json")["items"]
    open_items = [i for i in items if i["status"] in {"queued", "proposed"}]
    open_items.sort(key=lambda i: (-(i["impact"] * i["confidence"] / i["effort"]), i["id"]))
    done = [i for i in items if i["status"] not in {"queued", "proposed"}]

    lines = [
        "# Hardening queue",
        "",
        "Fixes to the repos people already see. Priority is impact x confidence / effort, per",
        "`RUBRIC.md` section 5. Machine readable source is `state/hardening.json`.",
        "",
        "| Priority | Repo | Fix | Defect |",
        "|---|---|---|---|",
    ]
    for i in open_items:
        priority = i["impact"] * i["confidence"] / i["effort"]
        lines.append(f"| {priority:.1f} | {i['repo']} | {i['title']} | {i['defect']} |")
    if done:
        lines += ["", "## Done", "", "| Repo | Fix |", "|---|---|"]
        for i in done:
            lines.append(f"| {i['repo']} | {i['title']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    targets = {
        ROOT / "README.md": render_readme(),
        ROOT / "BACKLOG.md": render_backlog(),
        ROOT / "HARDENING.md": render_hardening(),
    }

    stale = []
    for path, content in targets.items():
        current = path.read_text() if path.exists() else ""
        if current != content:
            stale.append(path.name)
            if not args.check:
                path.write_text(content)

    if args.check and stale:
        print(f"out of date: {', '.join(stale)}. Run python3 tools/render_readme.py")
        sys.exit(1)
    print(f"{'would update' if args.check else 'updated'}: {', '.join(stale) if stale else 'nothing'}")


if __name__ == "__main__":
    main()
