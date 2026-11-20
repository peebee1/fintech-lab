"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .bench import build, summarise, write_results


def main() -> None:
    ap = argparse.ArgumentParser(prog="qualification")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="price the gap and write results/")
    bench.add_argument("--seed", type=int, default=20261120)
    bench.add_argument("--out", type=Path, default=None, help="directory for summary.json and summary.md")

    show = sub.add_parser("show", help="print the headline without writing results")
    show.add_argument("--seed", type=int, default=20261120)

    args = ap.parse_args()
    if args.command == "bench":
        write_results(args.out, args.seed)
        for line in summarise(build(args.seed)):
            print(line)
        print(f"wrote {args.out or 'results/'}")
        return

    for line in summarise(build(args.seed)):
        print(line)


if __name__ == "__main__":
    main()
