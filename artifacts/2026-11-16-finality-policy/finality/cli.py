"""Command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bench import RESULTS, run_bench


def main() -> None:
    ap = argparse.ArgumentParser(prog="finality")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="run the evaluation and rewrite results/")
    bench.add_argument("--out", default=None, help="write results somewhere else")
    bench.add_argument("--json", action="store_true", help="print the payload")

    sub.add_parser("show", help="print the committed summary")

    args = ap.parse_args()

    if args.command == "bench":
        payload = run_bench(args.out)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for name, row in payload["policies"].items():
                print(
                    f"{name:<20} k median {row['k']['median']:>4} "
                    f"false credits {row['false_credits']:>3} "
                    f"lost USD {row['loss_usd']:>12,.2f} "
                    f"median wait {row['median_delay_s']:>6.0f}s"
                )
            failed = [k for k, ok in payload["checks"].items() if not ok]
            print("checks:", "all pass" if not failed else f"FAILED {failed}")
        return

    path: Path = RESULTS / "summary.json"
    payload = json.loads(path.read_text())
    print(json.dumps(payload["policies"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
