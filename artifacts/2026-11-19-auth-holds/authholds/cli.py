"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .bench import build, summarise, write_results


def main() -> None:
    ap = argparse.ArgumentParser(prog="authholds")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="sweep the capture window and write results/")
    bench.add_argument("--seed", type=int, default=20261119)
    bench.add_argument("--out", type=Path, default=None, help="directory for summary.json and summary.md")

    show = sub.add_parser("show", help="print the headline without writing results")
    show.add_argument("--seed", type=int, default=20261119)

    args = ap.parse_args()
    if args.command == "bench":
        payload = build(args.seed)
        write_results(args.out, payload)
        for line in summarise(payload):
            print(line)
        print(f"wrote {args.out or 'results/'}")
        return

    for line in summarise(build(args.seed)):
        print(line)


if __name__ == "__main__":
    main()
