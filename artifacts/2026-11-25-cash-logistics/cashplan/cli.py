"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .bench import build, render_markdown, summary_lines, write_results


def main() -> None:
    ap = argparse.ArgumentParser(prog="cashplan")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="replay every policy and write results/")
    bench.add_argument("--seed", type=int, default=20261125)
    bench.add_argument("--days", type=int, default=120)
    bench.add_argument("--out", type=Path, default=None, help="directory for summary.json and summary.md")

    show = sub.add_parser("show", help="print the headline without writing results")
    show.add_argument("--seed", type=int, default=20261125)
    show.add_argument("--days", type=int, default=120)

    args = ap.parse_args()
    summary = build(seed=args.seed, days=args.days)
    if args.command == "bench":
        target = write_results(args.out, summary)
        for line in summary_lines(summary):
            print(line)
        print(render_markdown(summary))
        print(f"wrote {target}")
        return
    for line in summary_lines(summary):
        print(line)


if __name__ == "__main__":
    main()
