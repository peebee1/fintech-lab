"""The measurements behind this artifact. Pure functions, one seed, no clock.

Four questions, four experiments:

1. Allocation. Given a total and a set of party weights, does the sum of the parts
   equal the total? Compared across four rounding strategies over synthetic payouts in
   three currencies with different minor unit exponents.
2. Bias. Which party benefits when the method does not balance, and by how much?
3. FX order. Does converting the pool once and then splitting agree with splitting and
   then converting each leg?
4. Invariants. Not a sample: every total from 0 to 240 against a fixed family of weight
   vectors, checking total preservation, per party deviation, and reconciliation.

Every number in results/ is produced here and nowhere else.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from . import fx
from .alloc import METHODS, exact_shares, reconcile
from .money import exponent

SEED = 20261028
TRIALS = 3000
CURRENCIES = ("USD", "JPY", "KWD")

# EUR base, synthetic snapshot. Kept as decimal strings because a rate is a quote.
RATES: dict[str, str] = {
    "USD": "1.0842",
    "JPY": "163.87",
    "KWD": "0.33371",
}

METHOD_NAMES = ("largest_remainder", "floor_to_largest", "naive_half_up", "naive_half_even")


@dataclass(frozen=True, slots=True)
class Payout:
    """One synthetic payout run: a total in minor units, split by integer weights."""

    currency: str
    total_minor: int
    weights: tuple[int, ...]


def make_payout(rng: random.Random) -> Payout:
    currency = rng.choice(CURRENCIES)
    parties = rng.randint(2, 5)
    weights = tuple(
        0 if rng.random() < 0.08 else rng.randint(1, 1000) for _ in range(parties)
    )
    if sum(weights) == 0:
        weights = tuple(1 for _ in range(parties))
    total = rng.randint(1, 250_000)
    return Payout(currency=currency, total_minor=total, weights=weights)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def _method_stats(payouts: Sequence[Payout], method: str) -> dict[str, Any]:
    rule = METHODS[method]
    mismatched = overpaid = underpaid = abs_total = max_abs = 0
    reconciliation_violations = 0
    for payout in payouts:
        parts = rule(payout.total_minor, payout.weights)
        record = reconcile(payout.total_minor, payout.weights, parts)
        if record.residual != record.explained:
            reconciliation_violations += 1
        if record.residual:
            mismatched += 1
            abs_total += abs(record.residual)
            max_abs = max(max_abs, abs(record.residual))
            if record.overpaid:
                overpaid += 1
            else:
                underpaid += 1
    return {
        "payouts": len(payouts),
        "mismatched": mismatched,
        "mismatch_pct": _pct(mismatched, len(payouts)),
        "overpaid": overpaid,
        "overpaid_pct": _pct(overpaid, len(payouts)),
        "underpaid": underpaid,
        "abs_residual_total": abs_total,
        "max_abs_residual": max_abs,
        "mean_abs_residual": round(abs_total / mismatched, 4) if mismatched else 0.0,
        "reconciliation_violations": reconciliation_violations,
    }


def allocation_experiment(seed: int = SEED, trials: int = TRIALS) -> dict[str, Any]:
    rng = random.Random(seed)
    payouts = [make_payout(rng) for _ in range(trials)]
    by_method = {name: _method_stats(payouts, name) for name in METHOD_NAMES}
    by_currency: dict[str, Any] = {}
    for currency in CURRENCIES:
        subset = [p for p in payouts if p.currency == currency]
        by_currency[currency] = {
            "minor_digits": exponent(currency),
            "payouts": len(subset),
            "methods": {name: _method_stats(subset, name) for name in METHOD_NAMES},
        }
    return {
        "seed": seed,
        "trials": trials,
        "currencies": list(CURRENCIES),
        "methods": by_method,
        "by_currency": by_currency,
    }


def bias_experiment(seed: int = SEED, trials: int = TRIALS) -> dict[str, Any]:
    """Who gets the missing unit, and how much of the payout moves.

    Excess is measured in basis points of the payout, because a minor unit of JPY and a
    minor unit of KWD are not the same quantity and adding them would be an FX rate
    nobody stated.
    """
    rng = random.Random(seed + 5)
    payouts = [make_payout(rng) for _ in range(trials)]
    by_method: dict[str, Any] = {}
    for name in METHOD_NAMES:
        rule = METHODS[name]
        favoured = 0
        bps: list[float] = []
        max_excess = Fraction(0)
        max_bps = 0.0
        for payout in payouts:
            parts = rule(payout.total_minor, payout.weights)
            exact = exact_shares(payout.total_minor, payout.weights)
            index = max(range(len(payout.weights)), key=lambda i: (payout.weights[i], -i))
            excess = Fraction(parts[index]) - exact[index]
            if excess > 0:
                favoured += 1
            max_excess = max(max_excess, excess)
            if payout.total_minor > 0:
                share_bps = float(excess / Fraction(payout.total_minor)) * 10_000
                bps.append(share_bps)
                max_bps = max(max_bps, share_bps)
        by_method[name] = {
            "payouts": len(payouts),
            "largest_party_overpaid": favoured,
            "largest_party_overpaid_pct": _pct(favoured, len(payouts)),
            "mean_excess_bps": round(sum(bps) / len(bps), 2) if bps else 0.0,
            "max_excess_bps": round(max_bps, 2),
            "max_excess_minor": float(round(max_excess, 6)),
        }
    return {"seed": seed + 5, "trials": trials, "methods": by_method}


def fx_order_experiment(seed: int = SEED, trials: int = TRIALS) -> dict[str, Any]:
    """Split then convert against convert then split, one target currency per payout."""
    rng = random.Random(seed + 1)
    per_target: dict[str, Any] = {
        target: {"payouts": 0, "disagreed": 0, "over": 0, "under": 0, "abs_total": 0, "max_abs": 0}
        for target in CURRENCIES
    }
    for _ in range(trials):
        base = make_payout(rng)
        target = rng.choice(CURRENCIES)
        rate = fx.parse_rate(RATES[target])
        converted_total, _ = fx.convert_then_split(
            base.total_minor, base.weights, "EUR", target, rate
        )
        legs = fx.split_then_convert(base.total_minor, base.weights, "EUR", target, rate)
        gap = sum(legs) - converted_total
        bucket = per_target[target]
        bucket["payouts"] += 1
        if gap:
            bucket["disagreed"] += 1
            bucket["abs_total"] += abs(gap)
            bucket["max_abs"] = max(bucket["max_abs"], abs(gap))
            bucket["over" if gap > 0 else "under"] += 1
    for bucket in per_target.values():
        bucket["disagreed_pct"] = _pct(bucket["disagreed"], bucket["payouts"])
        bucket["mean_abs_gap"] = (
            round(bucket["abs_total"] / bucket["disagreed"], 4) if bucket["disagreed"] else 0.0
        )
    total_payouts = sum(bucket["payouts"] for bucket in per_target.values())
    total_disagreed = sum(bucket["disagreed"] for bucket in per_target.values())
    return {
        "seed": seed + 1,
        "trials": trials,
        "source": "EUR",
        "rates": dict(RATES),
        "by_target": per_target,
        "payouts": total_payouts,
        "disagreed": total_disagreed,
        "disagreed_pct": _pct(total_disagreed, total_payouts),
        "max_abs_gap": max(bucket["max_abs"] for bucket in per_target.values()),
    }


WEIGHT_FAMILIES: tuple[tuple[int, ...], ...] = (
    (1, 1),
    (1, 1, 1),
    (1, 1, 1, 1),
    (1, 1, 1, 1, 1),
    (1, 2, 3),
    (7, 2, 1),
    (5, 3, 2),
    (1, 1, 1, 2),
    (13, 5, 1, 1),
    (2, 3, 5, 7, 11),
    (4, 4, 4, 4),
    (1, 0, 1),
    (0, 0, 1),
    (999, 1),
)

INVARIANT_MAX_TOTAL = 240


def invariant_experiment() -> dict[str, Any]:
    """Exhaustive over every total from 0 to 240 for each weight family. No sampling."""
    cases = 0
    total_violations = 0
    deviation_violations = 0
    reconciliation_violations = 0
    zero_weight_violations = 0
    naive_violations = 0
    worst_deviation = Fraction(0)
    for total in range(INVARIANT_MAX_TOTAL + 1):
        for weights in WEIGHT_FAMILIES:
            cases += 1
            parts = METHODS["largest_remainder"](total, weights)
            record = reconcile(total, weights, parts)
            if record.residual != record.explained:
                reconciliation_violations += 1
            if record.residual:
                total_violations += 1
            for weight, part, share in zip(weights, parts, exact_shares(total, weights)):
                deviation = abs(Fraction(part) - share)
                worst_deviation = max(worst_deviation, deviation)
                if deviation >= 1:
                    deviation_violations += 1
                if weight == 0 and part != 0:
                    zero_weight_violations += 1
            naive = METHODS["naive_half_up"](total, weights)
            if sum(naive) != total:
                naive_violations += 1
    return {
        "totals_checked": INVARIANT_MAX_TOTAL + 1,
        "weight_families": len(WEIGHT_FAMILIES),
        "cases": cases,
        "largest_remainder": {
            "total_violations": total_violations,
            "deviation_violations": deviation_violations,
            "reconciliation_violations": reconciliation_violations,
            "zero_weight_violations": zero_weight_violations,
            "worst_party_deviation": float(worst_deviation),
        },
        "naive_half_up": {
            "unbalanced_cases": naive_violations,
            "unbalanced_pct": _pct(naive_violations, cases),
        },
    }


def small_example() -> dict[str, Any]:
    """The example the README opens with: 100.00 USD split three ways."""
    weights = (1, 1, 1)
    total = 10_000
    rows = []
    for name in METHOD_NAMES:
        parts = METHODS[name](total, weights)
        rows.append(
            {
                "method": name,
                "parts": parts,
                "sum": sum(parts),
                "residual": total - sum(parts),
            }
        )
    return {"currency": "USD", "total_minor": total, "weights": list(weights), "rows": rows}


def run_all(seed: int = SEED, trials: int = TRIALS) -> dict[str, Any]:
    return {
        "seed": seed,
        "trials": trials,
        "allocation": allocation_experiment(seed, trials),
        "bias": bias_experiment(seed, trials),
        "fx_order": fx_order_experiment(seed, trials),
        "invariants": invariant_experiment(),
        "example": small_example(),
    }


def summary_text(payload: dict[str, Any]) -> str:
    allocation = payload["allocation"]
    methods = allocation["methods"]
    bias = payload["bias"]["methods"]
    fx_order = payload["fx_order"]
    invariants = payload["invariants"]
    example = payload["example"]
    balanced = invariants["largest_remainder"]

    lines = [
        "## Allocation over synthetic payouts",
        "",
        f"seed {payload['seed']}, {payload['trials']} payouts, currencies "
        f"{', '.join(allocation['currencies'])}.",
        "",
        "| Method | Unbalanced | Rate | Overpaid | Underpaid | Worst gap (minor) |",
        "|---|---|---|---|---|---|",
    ]
    for name in METHOD_NAMES:
        stats = methods[name]
        lines.append(
            f"| {name} | {stats['mismatched']} | {stats['mismatch_pct']}% | {stats['overpaid']} "
            f"| {stats['underpaid']} | {stats['max_abs_residual']} |"
        )
    lines += [
        "",
        "| Currency | Minor digits | naive_half_up unbalanced | largest_remainder unbalanced |",
        "|---|---|---|---|",
    ]
    for currency, block in allocation["by_currency"].items():
        naive = block["methods"]["naive_half_up"]
        lines.append(
            f"| {currency} | {block['minor_digits']} | {naive['mismatch_pct']}% | "
            f"{block['methods']['largest_remainder']['mismatch_pct']}% |"
        )
    lines += [
        "",
        "## Who gets the benefit",
        "",
        f"Same size, separate draw of {payload['trials']} payouts. Excess is the largest "
        "party's allocation minus that party's exact share, in basis points of the payout.",
        "",
        "| Method | Largest party overpaid | Rate | Mean excess (bps) | Worst excess (bps) | Worst excess (minor) |",
        "|---|---|---|---|---|---|",
    ]
    for name in METHOD_NAMES:
        stats = bias[name]
        lines.append(
            f"| {name} | {stats['largest_party_overpaid']} | {stats['largest_party_overpaid_pct']}% "
            f"| {stats['mean_excess_bps']} | {stats['max_excess_bps']} | {stats['max_excess_minor']} |"
        )
    lines += [
        "",
        "## Convert then split against split then convert",
        "",
        f"EUR source, {fx_order['payouts']} payouts, exact decimal rates.",
        "",
        "| Target | Payouts | Disagreed | Rate | Over | Under | Worst gap (minor) |",
        "|---|---|---|---|---|---|---|",
    ]
    for target, block in fx_order["by_target"].items():
        lines.append(
            f"| {target} | {block['payouts']} | {block['disagreed']} | {block['disagreed_pct']}% "
            f"| {block['over']} | {block['under']} | {block['max_abs']} |"
        )
    lines += [
        "",
        "## Exhaustive invariants",
        "",
        f"{invariants['cases']} cases: {invariants['totals_checked']} totals "
        f"(0 to {invariants['totals_checked'] - 1}) against "
        f"{invariants['weight_families']} weight families.",
        "",
        "| Check | Violations |",
        "|---|---|",
        f"| largest_remainder preserves the total | {balanced['total_violations']} |",
        f"| per party deviation under one minor unit | {balanced['deviation_violations']} |",
        f"| residual equals explained gap | {balanced['reconciliation_violations']} |",
        f"| zero weight party receives nothing | {balanced['zero_weight_violations']} |",
        f"| naive_half_up loses the total | {invariants['naive_half_up']['unbalanced_cases']} "
        f"({invariants['naive_half_up']['unbalanced_pct']}% of cases) |",
        "",
        "## One worked example",
        "",
        f"{example['total_minor']} minor units of {example['currency']} split by "
        f"weights {tuple(example['weights'])}.",
        "",
        "| Method | Parts | Sum | Residual |",
        "|---|---|---|---|",
    ]
    for row in example["rows"]:
        lines.append(
            f"| {row['method']} | {tuple(row['parts'])} | {row['sum']} | {row['residual']} |"
        )
    return "\n".join(lines)


def write_results(directory: Path, seed: int = SEED, trials: int = TRIALS) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    payload = run_all(seed, trials)
    for name in ("allocation", "bias", "fx_order", "invariants", "example"):
        text = json.dumps(payload[name], indent=2, sort_keys=True, default=str)
        (directory / f"{name}.json").write_text(text + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(summary_text(payload) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(summary_text(run_all()))
