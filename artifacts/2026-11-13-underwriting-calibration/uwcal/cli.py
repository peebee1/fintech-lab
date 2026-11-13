"""Command line entry point.

    PYTHONPATH=artifacts/2026-11-13-underwriting-calibration uv run python -m uwcal.cli run
    PYTHONPATH=artifacts/2026-11-13-underwriting-calibration uv run python -m uwcal.cli score preds.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from . import bench, book, ingest, metrics, policy
from .models import Scorecard, temper

RESULTS = Path(__file__).resolve().parents[1] / "results"


def write_results(directory: Path | None = None, seed: int = 13, n: int = 6000) -> dict:
    # Resolved inside the function: a default bound at import time would write
    # over committed results during a test run.
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = bench.run(seed=seed, n=n)
    (directory / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(
        "```\n" + bench.summary_text(payload) + "\n```\n", encoding="utf-8"
    )

    loans = book.build(seed=seed, n=n)
    parts = book.split(loans)
    card = Scorecard(l2=1.0).fit(parts["train"])
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    table = metrics.reliability_table(
        [temper(p, bench.SHARPEN) for p in preds], [loan.defaulted for loan in holdout]
    )
    with (directory / "reliability_overconfident.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0].keys()))
        writer.writeheader()
        writer.writerows(table)
    return payload


def score_file(path: Path | str, seed: int = 13, n: int = 6000) -> dict:
    """Score a predictions file from any model against the holdout slice."""
    loans = book.build(seed=seed, n=n)
    holdout = book.split(loans)["holdout"]
    preds = ingest.align(ingest.read_predictions(path), holdout)
    labels = [loan.defaulted for loan in holdout]
    report = metrics.all_metrics(preds, labels)
    report["policy"] = policy.evaluate(preds, holdout).as_dict()
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="uwcal", description="Underwriting calibration bench")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the bench and rewrite results/")
    run.add_argument("--seed", type=int, default=13)
    run.add_argument("--loans", type=int, default=6000)

    score = sub.add_parser("score", help="score a loan_id,pd predictions file")
    score.add_argument("predictions")
    score.add_argument("--seed", type=int, default=13)
    score.add_argument("--loans", type=int, default=6000)

    args = parser.parse_args(argv)

    if args.command == "run":
        payload = write_results(seed=args.seed, n=args.loans)
        print(bench.summary_text(payload))
    elif args.command == "score":
        print(json.dumps(score_file(args.predictions, seed=args.seed, n=args.loans), indent=2))


if __name__ == "__main__":
    main()
