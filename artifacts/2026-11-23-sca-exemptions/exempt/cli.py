"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .bench import render_markdown,run as build_summary, summarise, write_results


def main() -> None:
    ap = argparse.ArgumentParser(prog="exempt")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="replay every policy and write results/")
    bench.add_argument("--seed", type=int, default=20261123)
    bench.add_argument("--out", type=Path, default=None, help="directory for summary.json and summary.md")

    show = sub.add_parser("show", help="print the headline without writing results")
    show.add_argument("--seed", type=int, default=20261123)

    args = ap.parse_args()
    summary = build_summary(args.seed)
    if args.command == "bench":
        target = write_results(args.out, args.seed)
        for line in summarise(summary):
            print(line)
        print(render_markdown(summary))
        print(f"wrote {target}")
        return

    for line in summarise(summary):
        print(line)


if __name__ == "__main__":
    main()
