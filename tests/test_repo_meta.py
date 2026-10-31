"""Offline tests for tools/repo_meta.py.

No network: drift() is pure, and the live fetch is exercised by hand with --live.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import repo_meta  # noqa: E402


def entry(name: str = "demo", desc: str | None = None, topics: list[str] | None = None) -> dict:
    return {
        "repo": name,
        "description": desc if desc is not None else "A test repo that measures one thing and says so plainly.",
        "topics": topics if topics is not None else ["fintech", "payments", "python"],
    }


def test_committed_state_is_valid() -> None:
    problems = repo_meta.validate(repo_meta.load())
    assert problems == [], problems


def test_short_description_is_rejected() -> None:
    problems = repo_meta.validate({"repos": [entry(desc="too short")]})
    assert any("chars" in p for p in problems)


def test_em_dash_is_rejected() -> None:
    desc = "A repo about settlement \u2014 and the dash that is not allowed here at all."
    problems = repo_meta.validate({"repos": [entry(desc=desc)]})
    assert any("dash" in p for p in problems)


def test_topic_rules() -> None:
    assert any("lowercase" in p for p in repo_meta.validate({"repos": [entry(topics=["Fintech", "payments", "python"])]} ))
    assert any("2 topics" in p or "need 3" in p for p in repo_meta.validate({"repos": [entry(topics=["fintech", "payments"])]}))
    assert any("duplicate" in p for p in repo_meta.validate({"repos": [entry(topics=["fintech", "fintech", "python"])]}))
    assert any("duplicate repo" in p for p in repo_meta.validate({"repos": [entry(), entry()]}))


def test_drift_on_clean_state_is_empty() -> None:
    desired = {"repos": [entry(), entry(name="second", topics=["llm", "agents", "python"])]}
    observed = {r["repo"]: {"description": r["description"], "topics": r["topics"]} for r in desired["repos"]}
    assert repo_meta.drift(desired, observed) == []


def test_drift_ignores_topic_order() -> None:
    desired = {"repos": [entry(topics=["fintech", "payments", "python"])]}
    observed = {"demo": {"description": entry()["description"], "topics": ["python", "fintech", "payments"]}}
    assert repo_meta.drift(desired, observed) == []


def test_drift_names_missing_and_extra_topics() -> None:
    desired = {"repos": [entry(topics=["fintech", "payments", "python"])]}
    observed = {"demo": {"description": entry()["description"], "topics": ["fintech", "agents", "payments"]}}
    reported = repo_meta.drift(desired, observed)
    assert len(reported) == 1
    assert "missing python" in reported[0]
    assert "extra agents" in reported[0]


def test_drift_catches_description_change_and_absent_repo() -> None:
    desired = {"repos": [entry(), entry(name="gone")]}
    observed = {"demo": {"description": "Something else entirely, written later.", "topics": entry()["topics"]}}
    reported = repo_meta.drift(desired, observed)
    assert any("description differs" in r for r in reported)
    assert any("not found on GitHub" in r for r in reported)


def test_drift_is_deterministic() -> None:
    desired = {"repos": [entry(topics=["fintech", "payments", "python"])]}
    observed = {"demo": {"description": "x" * 50, "topics": ["zebra", "yak", "xenon"]}}
    first, second = repo_meta.drift(desired, observed), repo_meta.drift(desired, observed)
    assert first == second
    assert json.loads(json.dumps(first)) == first
