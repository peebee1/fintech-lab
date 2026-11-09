"""Command line entry point.

    PYTHONPATH=artifacts/2026-11-09-exchange-recon uv run python -m orderrecon.cli reconcile
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import bench

RESULTS = Path(__file__).resolve().parents[1] / "results"


def write_results(directory: Path | None = None, seed: int = 11, n_orders: int = 1200) -> dict:
    # Resolved inside the function so a test can point it at tmp_path without
    # the default argument capturing results/ at import time.
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = bench.run(seed=seed, n_orders=n_orders)
    (directory / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text("```\n" + bench.summary_text(payload) + "\n```\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="orderrecon", description="Broker, exchange, and book reconciliation")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("reconcile", help="run every policy and rewrite results/")
    run.add_argument("--seed", type=int, default=11)
    run.add_argument("--orders", type=int, default=1200)
    args = parser.parse_args(argv)

    payload = write_results(seed=args.seed, n_orders=args.orders)
    print(bench.summary_text(payload))
    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
