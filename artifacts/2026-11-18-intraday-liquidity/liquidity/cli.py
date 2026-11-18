"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from liquidity.bench import RESULTS, run_bench


def main() -> None:
    ap = argparse.ArgumentParser(prog="liquidity")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="run the evaluation and rewrite results/")
    bench.add_argument("--out", default=None, help="write results somewhere else")
    bench.add_argument("--json", action="store_true", help="print the payload")
    sub.add_parser("show", help="print the committed summary")

    args = ap.parse_args()

    if args.command == "bench":
        start = time.perf_counter()
        payload = run_bench(args.out)
        elapsed = time.perf_counter() - start
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return
        print(f"seed {payload['seed']}, {payload['eval_days']} scored days")
        for row in payload["policies"]:
            print(
                f"{row['policy']:<14} opening {row['mean_opening_usd']:>12,.0f} "
                f"annual {row['annual_total_usd']:>11,.0f} "
                f"failed {row['events']:>4} shorted {row['shortfall_rate'] * 100:>5.1f}%"
            )
        failed = [name for name, ok in payload["checks"].items() if not ok]
        print("checks:", "all pass" if not failed else f"FAILED {failed}")
        print(f"bench time: {elapsed:.1f}s")
        return

    path: Path = RESULTS / "summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(payload["policies"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
