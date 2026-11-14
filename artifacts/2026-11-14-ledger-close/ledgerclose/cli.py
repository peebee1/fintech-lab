"""One command: rebuild results/ from committed code."""

from __future__ import annotations

import argparse

from . import bench, inr


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ledgerclose", description="Append only ledger with a provable close")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("bench", help="run the bench and rewrite results/")
    run.add_argument("--seed", type=int, default=bench.SEED)
    run.add_argument("--out", default=None, help="directory for summary.json and summary.md")
    args = parser.parse_args(argv)

    payload = bench.run(directory=args.out, seed=args.seed)
    sealed = payload["sealed"]
    baseline = payload["baseline"]
    print(f"book: {payload['book']['entries']} transactions, gross {inr(payload['book']['gross_minor'])}")
    print(f"sealed: {sealed['closed_period_drift']['periods_drifted']} of {len(payload['closed_periods'])} closed "
          f"periods drifted, {sum(sealed['refusals'].values())} writes refused, "
          f"{sealed['closes_reproducing_before_tamper']} closes reproduce")
    print(f"baseline: {baseline['closed_period_drift']['periods_drifted']} of {len(payload['closed_periods'])} "
          f"drifted, {inr(baseline['closed_period_drift']['absolute_minor'])} absolute, "
          f"{baseline['closes_reproducing']} closes reproduce")
    print(f"tamper: chain broken at seq {sealed['chain']['broken_seq']}, "
          f"{sealed['closes_reproducing_after_tamper']} of {len(payload['closed_periods'])} closes still reproduce")


if __name__ == "__main__":
    main()
