"""Command line entry point.

    PYTHONPATH=artifacts/2026-11-11-dispute-clock uv run python -m disputeclock.cli run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import bench

RESULTS = Path(__file__).resolve().parents[1] / "results"


def write_results(directory: Path | None = None, seed: int = 11, n: int = 2000,
                  horizon: int = 360, budget: int = 40) -> dict:
    # Resolved inside the function so a test can point it at tmp_path without
    # the default argument capturing results/ at import time.
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = bench.run(seed=seed, n=n, horizon=horizon, budget=budget)
    (directory / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(
        "```\n" + bench.summary_text(payload) + "\n```\n", encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="disputeclock", description="Chargeback clock and evidence bench")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the ladder and rewrite results/")
    run.add_argument("--seed", type=int, default=11)
    run.add_argument("--cases", type=int, default=2000)
    run.add_argument("--horizon", type=int, default=360)
    run.add_argument("--budget", type=int, default=40)
    args = parser.parse_args(argv)

    payload = write_results(seed=args.seed, n=args.cases, horizon=args.horizon, budget=args.budget)
    print(bench.summary_text(payload))
    print(f"\nwrote {RESULTS}")
    if not payload["passed"]:
        raise SystemExit("a bench check failed")


if __name__ == "__main__":
    main()
