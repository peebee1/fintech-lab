"""Command line entry point.

    PYTHONPATH=artifacts/2026-11-04-sanctions-screening uv run python -m screenlab.cli screen
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import bench

RESULTS = Path(__file__).resolve().parents[1] / "results"


def write_results(directory: Path | None = None, budget: int = bench.REVIEW_BUDGET,
                  dataset=None) -> dict:
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = bench.run(dataset=dataset, budget=budget)
    (directory / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(
        "```\n" + bench.summary_text(payload) + "\n```\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="screenlab", description="Sanctions screening bench")
    sub = parser.add_subparsers(dest="command", required=True)
    screen = sub.add_parser("screen", help="screen the synthetic book and rewrite results/")
    screen.add_argument("--budget", type=int, default=bench.REVIEW_BUDGET)
    args = parser.parse_args(argv)

    payload = write_results(budget=args.budget)
    print(bench.summary_text(payload))
    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
