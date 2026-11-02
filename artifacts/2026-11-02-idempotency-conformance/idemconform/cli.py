"""Command line entry point.

    PYTHONPATH=. uv run python -m idemconform.cli run
    PYTHONPATH=. uv run python -m idemconform.cli overhead
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import suite

RESULTS = Path(__file__).resolve().parents[1] / "results"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_results(directory: Path | None = None) -> dict:
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    payload = suite.run_all()
    _write(directory / "conformance.json", payload)
    _write(directory / "violations.json", {"meta": payload["meta"], "violations": payload["violations"]})
    _write(directory / "overhead.json", suite.measure_overhead())
    (directory / "summary.md").write_text(
        "```\n" + suite.summary_text(payload) + "\n```\n", encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="idemconform", description="Idempotency conformance suite")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run every check against every implementation and rewrite results/")
    overhead = sub.add_parser("overhead", help="time the key store overhead")
    overhead.add_argument("-n", type=int, default=20_000)
    args = parser.parse_args(argv)

    if args.command == "run":
        payload = write_results()
        print(suite.summary_text(payload))
        print(f"\nwrote {RESULTS}")
    else:
        print(json.dumps(suite.measure_overhead(args.n), indent=2))


if __name__ == "__main__":
    main()
