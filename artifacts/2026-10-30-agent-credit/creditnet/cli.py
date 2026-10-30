"""Command line entry point.

    python -m creditnet.cli bench
    python -m creditnet.cli window 3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import sim
from .credit import RULES
from .money import fmt

RESULTS = Path(__file__).resolve().parents[1] / "results"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_results(directory: Path | None = None, seed: int = sim.SEED, scenarios: int = sim.SCENARIOS) -> dict:
    payload = sim.experiments(seed=seed, scenarios=scenarios)
    directory = RESULTS if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)

    _write(directory / "summary.json", payload)
    _write(
        directory / "netting.json",
        {"meta": payload["meta"], "netting": payload["netting"], "windows": payload["windows"]},
    )
    _write(
        directory / "limits.json",
        {"meta": payload["meta"], "reference": payload["reference"], "sweep": payload["sweep"]},
    )
    _write(
        directory / "policies.json",
        {
            "meta": payload["meta"],
            "reference_limit": payload["meta"]["reference_limit"],
            "policies": payload["reference"]["rules"],
        },
    )
    _write(
        directory / "default.json",
        {"meta": payload["meta"], "default": payload["default"], "reference_limit": payload["meta"]["reference_limit"]},
    )
    (directory / "summary.md").write_text(
        f"```\n{sim.summary_text(payload)}\n```\n", encoding="utf-8"
    )
    return payload


def show_window(index: int, limit: int = sim.REFERENCE_LIMIT, seed: int = sim.SEED) -> None:
    record = sim.window(index, limit, seed=seed)
    print(f"window {index}: {record['offered']} obligations, gross {fmt(record['offered_value'])}, "
          f"limit {fmt(limit)}")
    print(f"  bilateral settle    {fmt(record['bilateral_value'])}")
    print(f"  multilateral settle {fmt(record['multilateral_value'])}  "
          f"(-{record['netting_reduction_pct']:.2f}%)")
    print(f"  largest debtor {record['victim']} owes {fmt(record['victim_net_debit'])} "
          f"after sending {fmt(record['victim_gross_outflow'])}")
    print()
    print(f"  {'rule':<12}{'admitted':>12}{'rejected':>12}{'max debit':>12}{'loss':>10}")
    for rule in RULES:
        entry = record["policies"][rule]
        print(f"  {rule:<12}{fmt(entry['admitted_value']):>12}{fmt(entry['rejected_value']):>12}"
              f"{fmt(entry['max_net_debit']):>12}{fmt(entry['default_loss']):>10}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="creditnet", description="Agent credit limits and netting")
    sub = parser.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="recompute every number and rewrite results/")
    bench.add_argument("--seed", type=int, default=sim.SEED)
    bench.add_argument("--scenarios", type=int, default=sim.SCENARIOS)

    single = sub.add_parser("window", help="print one settlement window in detail")
    single.add_argument("index", type=int)
    single.add_argument("--limit", type=int, default=sim.REFERENCE_LIMIT)
    single.add_argument("--seed", type=int, default=sim.SEED)

    args = parser.parse_args(argv)
    if args.command == "bench":
        payload = write_results(seed=args.seed, scenarios=args.scenarios)
        print(sim.summary_text(payload))
        print(f"\nwrote {RESULTS}")
    else:
        show_window(args.index, limit=args.limit, seed=args.seed)


if __name__ == "__main__":
    main()
