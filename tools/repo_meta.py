#!/usr/bin/env python3
"""Declare and verify the public surface of every public repo on peebee1.

state/repo_meta.json is the desired state: one description and one topic list per
public repo. The defect this closes is drift. Topics were added by hand to two
repos and never to the rest, and several descriptions grew into feature piles
that read like notes to self rather than a thesis a stranger can act on.

Usage:
    python3 tools/repo_meta.py             # validate state/repo_meta.json, no network
    python3 tools/repo_meta.py --live      # compare against GitHub, exit 1 on drift
    python3 tools/repo_meta.py --apply     # write the desired state to GitHub
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "repo_meta.json"
OWNER = "peebee1"

MAX_DESC = 350
MIN_DESC = 40
MIN_TOPICS = 3
MAX_TOPICS = 20
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
BANNED_DASHES = ("\u2014", "\u2013")


def load(path: Path | None = None) -> dict:
    return json.loads((STATE if path is None else Path(path)).read_text())


def topic_problems(repo: str, topics: list[str]) -> list[str]:
    problems: list[str] = []
    if not isinstance(topics, list):
        return [f"{repo}: topics must be a list"]
    if not MIN_TOPICS <= len(topics) <= MAX_TOPICS:
        problems.append(f"{repo}: {len(topics)} topics, need {MIN_TOPICS} to {MAX_TOPICS}")
    seen = [t.lower() for t in topics]
    if len(seen) != len(set(seen)):
        problems.append(f"{repo}: duplicate topic")
    for t in topics:
        if not isinstance(t, str) or not TOPIC_RE.match(t):
            problems.append(f"{repo}: topic {t!r} must be lowercase letters, digits and hyphens")
    return problems


def validate(doc: dict) -> list[str]:
    """Return every rule violation in the desired state. Empty list means valid."""
    problems: list[str] = []
    repos = doc.get("repos")
    if not isinstance(repos, list) or not repos:
        return ["state has no repos list"]
    names = [r.get("repo", "") for r in repos]
    if len(names) != len(set(names)):
        problems.append("duplicate repo name in state")
    for r in repos:
        name = r.get("repo", "")
        if not name:
            problems.append("entry with no repo name")
            continue
        desc = r.get("description", "")
        if not isinstance(desc, str):
            problems.append(f"{name}: description must be a string")
            continue
        if not MIN_DESC <= len(desc) <= MAX_DESC:
            problems.append(f"{name}: description is {len(desc)} chars, need {MIN_DESC} to {MAX_DESC}")
        if any(d in desc for d in BANNED_DASHES):
            problems.append(f"{name}: description contains an em or en dash")
        if desc != desc.strip() or "  " in desc:
            problems.append(f"{name}: description has stray whitespace")
        problems.extend(topic_problems(name, r.get("topics", [])))
    return problems


def drift(desired: dict, observed: dict) -> list[str]:
    """Compare desired state to an observed snapshot keyed by repo name.

    Topic order is not meaningful, so compare sets. A repo missing from the
    snapshot counts as drift rather than being skipped, because a renamed or
    deleted repo is exactly the silent failure this check exists to catch.
    """
    out: list[str] = []
    for r in desired["repos"]:
        name = r["repo"]
        seen = observed.get(name)
        if seen is None:
            out.append(f"{name}: not found on GitHub")
            continue
        want_topics, have_topics = set(r["topics"]), set(seen.get("topics") or [])
        if want_topics != have_topics:
            missing = sorted(want_topics - have_topics)
            extra = sorted(have_topics - want_topics)
            parts = []
            if missing:
                parts.append("missing " + ",".join(missing))
            if extra:
                parts.append("extra " + ",".join(extra))
            out.append(f"{name}: topics {', '.join(parts)}")
        if (seen.get("description") or "") != r["description"]:
            out.append(f"{name}: description differs")
    return out


def gh(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args], input=stdin, capture_output=True, text=True, check=False
    )


def fetch_live(owner: str = OWNER) -> dict:
    """Read the current description and topics of every repo in the state file."""
    out: dict[str, dict] = {}
    for r in load()["repos"]:
        name = r["repo"]
        got = gh("api", f"repos/{owner}/{name}")
        if got.returncode != 0:
            continue
        meta = json.loads(got.stdout)
        topics = gh("api", f"repos/{owner}/{name}/topics")
        names = json.loads(topics.stdout).get("names", []) if topics.returncode == 0 else []
        out[name] = {"description": meta.get("description") or "", "topics": names}
    return out


def apply_live(owner: str = OWNER) -> list[str]:
    """Write the desired state to GitHub and return the list of repos changed."""
    changed: list[str] = []
    for r in load()["repos"]:
        name = r["repo"]
        body = json.dumps({"description": r["description"]})
        got = gh("api", "-X", "PATCH", f"repos/{owner}/{name}", "--input", "-", stdin=body)
        if got.returncode != 0:
            print(f"{name}: description write failed: {got.stderr.strip()}", file=sys.stderr)
            continue
        body = json.dumps({"names": r["topics"]})
        got = gh("api", "-X", "PUT", f"repos/{owner}/{name}/topics", "--input", "-", stdin=body)
        if got.returncode != 0:
            print(f"{name}: topic write failed: {got.stderr.strip()}", file=sys.stderr)
            continue
        changed.append(name)
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="compare state to GitHub, exit 1 on drift")
    ap.add_argument("--apply", action="store_true", help="write state to GitHub")
    ap.add_argument("--state", default=None, help="path to a state file")
    args = ap.parse_args(argv)

    doc = load(args.state)
    problems = validate(doc)
    if problems:
        for p in problems:
            print(f"invalid: {p}")
        return 1
    print(f"state ok: {len(doc['repos'])} repos, {sum(len(r['topics']) for r in doc['repos'])} topics")

    if args.apply:
        changed = apply_live()
        print(f"applied: {len(changed)} of {len(doc['repos'])} repos written")
        return 0 if len(changed) == len(doc["repos"]) else 1

    if args.live:
        differences = drift(doc, fetch_live())
        if differences:
            for d in differences:
                print(f"drift: {d}")
            return 1
        print(f"live ok: {len(doc['repos'])} repos match state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
