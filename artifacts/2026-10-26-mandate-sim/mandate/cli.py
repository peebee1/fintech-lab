"""Command line entry point.

    PYTHONPATH=artifacts/2026-10-26-mandate-sim uv run python -m mandate.cli eval

One command runs the book, the three planners, the sensitivity sweep, the
reconciliation check, and writes results/eval.md plus results/eval.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evals import lag_sensitivity, reconcile, summarise, to_markdown, to_payload
from .sim import PLANNERS, build_population, plan_all

ARTIFACT = Path(__file__).resolve().parents[1]
RESULTS = ARTIFACT / "results"


def _eval() -> None:
    population = build_population()
    results = plan_all(population)
    metrics = [summarise(results[pid], population) for pid in PLANNERS]
    sensitivity = lag_sensitivity(population)

    for m in metrics:
        ok, notes = reconcile(m)
        if not ok:
            raise SystemExit(f"reconciliation failed for {m.planner}: {notes}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "eval.md").write_text(to_markdown(metrics, population, sensitivity))
    (RESULTS / "eval.json").write_text(
        json.dumps(to_payload(metrics, population, sensitivity), indent=2)
    )
    print(to_markdown(metrics, population, sensitivity))
    print("wrote results/eval.md and results/eval.json")


def main() -> None:
    ap = argparse.ArgumentParser(prog="mandate")
    ap.add_argument("command", choices=["eval"])
    ap.parse_args()
    _eval()


if __name__ == "__main__":
    main()
