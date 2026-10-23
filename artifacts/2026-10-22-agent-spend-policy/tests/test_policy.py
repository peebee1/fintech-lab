"""Deterministic tests for the spend policy engine.

The policy logic ships as policy.mjs, so the tests execute that exact file through
node rather than a Python reimplementation. No network, no clock, no sleeps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CASES = HERE / "cases.json"
HARNESS = HERE / "harness.mjs"


def run_harness() -> list[dict]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    assert node
    proc = subprocess.run(
        [node, str(HARNESS), str(CASES)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_cases_file_is_valid() -> None:
    cases = json.loads(CASES.read_text())
    assert len(cases) >= 8
    for case in cases:
        assert {"name", "intent", "ctx", "expect"} <= set(case)


def test_all_cases_pass() -> None:
    failures = [r for r in run_harness() if not r["pass"]]
    assert not failures, failures


@pytest.mark.parametrize(
    "name",
    [
        "small charge within budget",
        "over per transaction cap",
        "merchant not allowlisted",
        "above approval threshold",
        "would exceed remaining budget",
        "velocity limit on repeat charges",
        "outside settlement window",
    ],
)
def test_named_behaviour(name: str) -> None:
    results = {r["name"]: r for r in run_harness()}
    assert name in results
    assert results[name]["pass"], results[name]


def test_deterministic_across_runs() -> None:
    assert run_harness() == run_harness()
