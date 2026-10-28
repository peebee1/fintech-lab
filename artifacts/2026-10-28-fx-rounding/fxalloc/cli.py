"""Command line entry point.

    python -m fxalloc.cli bench
    python -m fxalloc.cli split 10000 USD 1 1 1
"""

from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from . import bench
from .alloc import METHODS, exact_shares, reconcile
from .money import Money

RESULTS = Path(__file__).resolve().parents[1] / "results"
METHOD_NAMES = ("largest_remainder", "floor_to_largest", "naive_half_up", "naive_half_even")


def _split(args: argparse.Namespace) -> None:
    money = Money(args.currency, args.total)
    weights = tuple(args.weights)
    print(f"{money} split by weights {weights}\n")
    shares = exact_shares(args.total, weights)
    for index, share in enumerate(shares):
        print(f"  party {index}: exact {float(share):.6f}")
    print()
    for name in METHOD_NAMES:
        parts = METHODS[name](args.total, weights)
        record = reconcile(args.total, weights, parts)
        rendered = [Money(args.currency, part).format() for part in parts]
        verdict = "balanced" if record.balanced else f"off by {record.residual} minor units"
        print(f"  {name:<18} {rendered}  {verdict}")
    print(f"\nExact share total: {float(sum(shares, Fraction(0))):.6f}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fxalloc", description="Exact money allocation")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("bench", help="recompute every number and rewrite results/")
    run.add_argument("--seed", type=int, default=bench.SEED)
    run.add_argument("--trials", type=int, default=bench.TRIALS)

    example = sub.add_parser("split", help="show one amount under every method")
    example.add_argument("total", type=int, help="amount in minor units")
    example.add_argument("currency", nargs="?", default="USD")
    example.add_argument("weights", nargs="+", type=int)

    args = parser.parse_args(argv)
    if args.command == "bench":
        payload = bench.write_results(RESULTS, seed=args.seed, trials=args.trials)
        print(bench.summary_text(payload))
        print(f"\nwrote {RESULTS}")
    else:
        _split(args)


if __name__ == "__main__":
    main()
