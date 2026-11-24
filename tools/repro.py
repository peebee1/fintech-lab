#!/usr/bin/env python3
"""Re-derive an artifact's committed results from its committed code.

Every artifact README quotes numbers. The test suite proves the code runs, and
gate.py proves that results/ holds files, but nothing has ever proved that the
committed files still come from the committed code. A hand-edited summary.json, or
a results file left behind by a refactor, passes every check the lab runs today.

This tool copies an artifact into a scratch directory, runs the documented command
there, and compares what came out with what is committed. Two comparison classes:

    byte       the file must match exactly. These are the numbers the README quotes.
    structure  the JSON key tree and leaf types must match, values are reported as
               drift and do not fail. These are wall clock timings, and a shared CI
               runner is not the machine that recorded them. Gating a value there
               would gate the runner, not the code.
    volatile   must be produced by the command and committed, bytes not compared.
               A rendered table with a timing column lives here. It is declared
               ungated on purpose rather than pretending to pass a byte check.

Usage:
    python3 tools/repro.py artifacts/2026-11-23-sca-exemptions
    python3 tools/repro.py --all
    python3 tools/repro.py --all --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "repro_manifest.json"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".venv")


@dataclass
class Report:
    artifact: str
    ran: bool = False
    command: str = ""
    failures: list[str] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    compared: int = 0
    volatile: int = 0

    @property
    def ok(self) -> bool:
        return self.ran and not self.failures


def load_manifest(path: Path = MANIFEST) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def entry_for(artifact_dir: Path, manifest: dict) -> dict | None:
    """Find the manifest entry for a directory, keyed by its path from the lab root."""
    artifact_dir = artifact_dir.resolve()
    for key, entry in manifest.items():
        if (ROOT / key).resolve() == artifact_dir:
            return entry
    return None


def _resolve(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("empty argv")
    if argv[0] == "python":
        return [sys.executable, *argv[1:]]
    exe = shutil.which(argv[0])
    if exe is None:
        raise FileNotFoundError(f"{argv[0]} not on PATH")
    return [exe, *argv[1:]]


def _leaf_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    return "object"


def _walk(committed, produced, path: str, failures: list[str], drift: list[str]) -> None:
    """Compare JSON key trees and leaf types; report numeric drift without failing."""
    kind_c, kind_p = _leaf_type(committed), _leaf_type(produced)
    if kind_c != kind_p:
        failures.append(f"{path}: type {kind_c} committed, {kind_p} produced")
        return
    if kind_c == "object":
        missing = sorted(set(committed) - set(produced))
        extra = sorted(set(produced) - set(committed))
        if missing:
            failures.append(f"{path}: keys missing from produced output: {', '.join(missing)}")
        if extra:
            failures.append(f"{path}: unexpected keys in produced output: {', '.join(extra)}")
        for key in sorted(set(committed) & set(produced)):
            _walk(committed[key], produced[key], f"{path}.{key}", failures, drift)
        return
    if kind_c == "list":
        if len(committed) != len(produced):
            failures.append(f"{path}: {len(committed)} items committed, {len(produced)} produced")
        for i, (a, b) in enumerate(zip(committed, produced)):
            _walk(a, b, f"{path}[{i}]", failures, drift)
        return
    if kind_c == "number" and committed:
        delta = (produced - committed) / abs(committed) * 100.0
        if abs(delta) >= 0.05:
            drift.append(f"{path}: {committed} committed, {produced} produced ({delta:+.1f}%)")


def reproduce(artifact_dir: Path, entry: dict, workdir: Path | None = None) -> Report:
    """Run one manifest entry against a scratch copy. Pure apart from the subprocess."""
    artifact_dir = Path(artifact_dir).resolve()
    report = Report(artifact=artifact_dir.name)
    steps = entry.get("steps") or []
    if not steps:
        report.failures.append("manifest entry has no steps")
        return report

    tmp = Path(workdir) if workdir is not None else Path(tempfile.mkdtemp(prefix="repro-"))
    work = tmp / artifact_dir.name
    try:
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(artifact_dir, work, ignore=SKIP)

        env = dict(os.environ)
        env.update({"PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1", "TZ": "UTC"})
        for i, step in enumerate(steps, 1):
            argv = _resolve(list(step["argv"]))
            report.command = " ".join(step["argv"])
            # Remove the committed outputs first, so a file the command never writes
            # cannot survive the copy and pass as reproduced.
            for rel in [*step.get("byte", []), *step.get("structure", []), *step.get("volatile", [])]:
                (work / rel).unlink(missing_ok=True)
            proc = subprocess.run(
                argv, cwd=work, env=env, capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
                report.failures.append(
                    f"step {i} exited {proc.returncode}: " + " | ".join(tail)
                )
                continue
            report.ran = True
            for rel in step.get("byte", []):
                committed = artifact_dir / rel
                produced = work / rel
                if not produced.exists():
                    report.failures.append(f"{rel}: not produced by the command")
                    continue
                if not committed.exists():
                    report.failures.append(f"{rel}: produced but not committed")
                    continue
                report.compared += 1
                if committed.read_bytes() != produced.read_bytes():
                    report.failures.append(f"{rel}: committed file does not reproduce from code")
            for rel in step.get("structure", []):
                committed = artifact_dir / rel
                produced = work / rel
                if not produced.exists():
                    report.failures.append(f"{rel}: not produced by the command")
                    continue
                if not committed.exists():
                    report.failures.append(f"{rel}: produced but not committed")
                    continue
                report.compared += 1
                _walk(
                    json.loads(committed.read_text(encoding="utf-8")),
                    json.loads(produced.read_text(encoding="utf-8")),
                    rel,
                    report.failures,
                    report.drift,
                )
            for rel in step.get("volatile", []):
                if not (work / rel).exists():
                    report.failures.append(f"{rel}: not produced by the command")
                    continue
                if not (artifact_dir / rel).exists():
                    report.failures.append(f"{rel}: produced but not committed")
                    continue
                report.volatile += 1
    finally:
        if workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    manifest = load_manifest()
    if args.all:
        targets = [ROOT / key for key in sorted(manifest)]
    elif args.path:
        targets = [Path(args.path).expanduser()]
    else:
        ap.error("give a path or --all")

    reports = []
    for target in targets:
        entry = entry_for(target, manifest)
        if entry is None:
            reports.append(Report(artifact=target.name, failures=["no manifest entry"]))
            continue
        reports.append(reproduce(target, entry))

    if args.json:
        print(json.dumps(
            [
                {
                    "artifact": r.artifact,
                    "ok": r.ok,
                    "command": r.command,
                    "compared": r.compared,
                    "volatile": r.volatile,
                    "failures": r.failures,
                    "drift": r.drift,
                }
                for r in reports
            ],
            indent=2,
        ))
    else:
        for r in reports:
            extra = f", {r.volatile} declared volatile" if r.volatile else ""
            print(f"{'PASS' if r.ok else 'FAIL'}  {r.artifact}  {r.compared} files  {r.command}{extra}")
            for item in r.failures:
                print(f"      {item}")
            for item in r.drift:
                print(f"      drift {item}")
        print(f"\n{sum(r.ok for r in reports)}/{len(reports)} artifacts reproduce")
    sys.exit(0 if all(r.ok for r in reports) else 1)


if __name__ == "__main__":
    main()
