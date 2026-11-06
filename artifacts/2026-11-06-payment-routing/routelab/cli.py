"""Command line entry point.

    PYTHONPATH=artifacts/2026-11-06-payment-routing uv run python -m routelab.cli route
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import bench

RESULTS = Path(__file__).resolve().parents[1] / "results"


def write_results(directory: Path | None = None, n: int = 50000) -> dict:
    # Resolved inside the function so a test can point it at tmp_path without
    # the default argument capturing results/ at import time.
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = bench.run_all(n=n)
    (directory / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text("```\n" + bench.summary_text(payload) + "\n```\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="routelab", description="Authorization aware routing bench")
    sub = parser.add_subparsers(dest="command", required=True)
    route = sub.add_parser("route", help="run every policy and rewrite results/")
    route.add_argument("--n", type=int, default=50000)
    args = parser.parse_args(argv)

    payload = write_results(n=args.n)
    print(bench.summary_text(payload))
    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
