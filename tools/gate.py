#!/usr/bin/env python3
"""Quality gate for an artifact or a repo directory.

Binary checks from RUBRIC.md section 1. Exit code 0 means shippable.
Exit code 1 means park it, do not push.

Usage:
    python3 tools/gate.py artifacts/2026-10-23-recon
    python3 tools/gate.py artifacts/2026-10-23-recon --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt", ".cfg", ".sh", ".html", ".csv"}

REQUIRED_SECTIONS = {
    "problem": r"^#{2,3}\s*.*\bproblem\b",
    "why": r"^#{2,3}\s*.*\b(why it matters|why)\b",
    "design": r"^#{2,3}\s*.*\b(design|how it works|approach)\b",
    "run": r"^#{2,3}\s*.*\b(run|quickstart|usage|getting started)\b",
    "results": r"^#{2,3}\s*.*\b(results|measurements|numbers)\b",
    "limits": r"^#{2,3}\s*.*\b(limits|limitations|what this does not do)\b",
    "next": r"^#{2,3}\s*.*\b(next|roadmap|what i would do next)\b",
}

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI style key"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub personal token"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine grained token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key block"),
    (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{16,}['\"]", "hardcoded credential"),
    (r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{24,}", "hardcoded bearer token"),
]


def iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def check_readme(base: Path) -> tuple[bool, str]:
    readme = base / "README.md"
    if not readme.exists():
        return False, "no README.md"
    text = readme.read_text(encoding="utf-8", errors="ignore")
    missing = [
        name for name, pattern in REQUIRED_SECTIONS.items()
        if not re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    ]
    if missing:
        return False, f"README missing sections: {', '.join(missing)}"
    return True, "README has all required sections"


def check_secrets(base: Path) -> tuple[bool, str]:
    hits = []
    for path in iter_files(base):
        if path.name in {".env", ".env.local"}:
            hits.append(f"{path.relative_to(base)} (env file)")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, text):
                hits.append(f"{path.relative_to(base)} ({label})")
    if hits:
        return False, "possible secrets: " + ", ".join(hits[:5])
    return True, "no secrets found"


def check_size(base: Path) -> tuple[bool, str]:
    loc = 0
    for path in base.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        loc += len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    if loc > 1500:
        return False, f"{loc} python lines, over the 1500 cap (split the idea)"
    return True, f"{loc} python lines"


def check_results(base: Path) -> tuple[bool, str]:
    for candidate in ("results", "bench", "eval"):
        directory = base / candidate
        if directory.is_dir() and any(p.is_file() for p in directory.rglob("*")):
            return True, f"measured output in {candidate}/"
    return False, "no results/, bench/, or eval/ output committed"


def check_portable(base: Path) -> tuple[bool, str]:
    """A demo that needs the network is a demo that stops working. Tests and runtime only."""
    banned = ("requests", "httpx", "aiohttp", "urllib.request", "boto3", "openai", "anthropic")
    hits = []
    for path in base.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in banned:
            if re.search(rf"^\s*(import|from)\s+{re.escape(name)}\b", text, re.MULTILINE):
                hits.append(f"{path.name}:{name}")
    if hits:
        return False, "network or vendor dependency: " + ", ".join(hits[:4])
    return True, "no network or vendor dependencies in code"


def run_tests(base: Path) -> tuple[bool, str]:
    if not (base / "tests").is_dir():
        return False, "no tests/ directory"

    def once() -> tuple[int, str]:
        proc = subprocess.run(
            ["uv", "run", "--project", str(ROOT), "pytest", "-q", str(base)],
            cwd=ROOT, capture_output=True, text=True, timeout=600,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        return proc.returncode, tail[-1] if tail else ""

    code_one, line_one = once()
    if code_one != 0:
        return False, f"tests failed: {line_one}"
    code_two, line_two = once()
    if code_two != 0:
        return False, f"tests failed on rerun: {line_two}"
    if line_one != line_two:
        return False, f"nondeterministic summary: '{line_one}' then '{line_two}'"
    return True, line_one


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    base = Path(args.path).expanduser().resolve()
    if not base.is_dir():
        sys.exit(f"not a directory: {base}")

    checks = [
        ("G1 runnable", lambda: (True, "checked by G2 and the README run section")),
        ("G2 tested", lambda: run_tests(base)),
        ("G3 measured", lambda: check_results(base)),
        ("G4 honest", lambda: check_secrets(base)),
        ("G5 documented", lambda: check_readme(base)),
        ("G6 portable", lambda: check_portable(base)),
        ("G7 scoped", lambda: check_size(base)),
    ]

    results = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except subprocess.TimeoutExpired:
            ok, detail = False, "timed out"
        results.append({"gate": name, "ok": ok, "detail": detail})

    passed = all(r["ok"] for r in results)
    if args.json:
        print(json.dumps({"path": str(base), "passed": passed, "results": results}, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['gate']:<14} {r['detail']}")
        print(f"\n{'SHIPPABLE' if passed else 'PARK IT'}: {base.name}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
