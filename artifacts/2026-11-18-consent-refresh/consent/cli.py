"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from consent.bench import RESULTS, run_bench


def main() -> None:
    ap = argparse.ArgumentParser(prog="consent")
    sub = ap.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="run the evaluation and rewrite results/")
    bench.add_argument("--out", default=None, help="write results somewhere else")
    bench.add_argument("--json", action="store_true", help="print the payload")
    bench.add_argument("--size", type=int, default=None, help="payer count, for a quick check")

    sub.add_parser("show", help="print the committed summary")

    args = ap.parse_args()

    if args.command == "bench":
        start = time.perf_counter()
        payload = run_bench(args.out, size=args.size) if args.size else run_bench(args.out)
        elapsed = time.perf_counter() - start
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for row in payload["policies"]:
                print(
                    f"{row['policy']:<16} capture {row['capture_rate'] * 100:>5.1f}% "
                    f"captured USD {row['captured_usd']:>12,.2f} "
                    f"refused {row['refused']:>4} prompts {row['prompts']:>5} "
                    f"abandon/prompt {row['abandon_rate_per_prompt'] * 100:>5.1f}%"
                )
            failed = [name for name, ok in payload["checks"].items() if not ok]
            print("checks:", "all pass" if not failed else f"FAILED {failed}")
            print(f"bench time: {elapsed:.1f}s")
        return

    path: Path = RESULTS / "summary.json"
    payload = json.loads(path.read_text())
    print(json.dumps(payload["policies"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
