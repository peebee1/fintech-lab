"""Bench: nine sizing policies on one float book, a percentile sweep, three
regimes, a fee sensitivity, and a settlement schedule experiment.

Walk forward. A policy sizing day i sees days 0..i-1 only. Days 0..WARMUP-1 are
burn in and are never scored, so no result here reads its own answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from liquidity.book import BookParams, Day, book_totals, build_book
from liquidity.policy import (
    DailyNetMean,
    DailyNetP95,
    GrossBatch,
    Oracle,
    PeakPercentile,
    Policy,
    Zero,
)
from liquidity.sim import (
    CARRY_BPS_PER_DAY,
    DEFAULT_EMERGENCY_BPS,
    DEFAULT_FEE_CENTS,
    DayResult,
    required_opening,
    simulate_day,
    totals,
)

RESULTS = Path(__file__).resolve().parent.parent / "results"
SEED = 20261118
WARMUP = 60
TRADING_DAYS = 252


def policies() -> list[Policy]:
    return [
        Zero(),
        DailyNetMean(),
        DailyNetP95(),
        GrossBatch(),
        PeakPercentile(0.50),
        PeakPercentile(0.75),
        PeakPercentile(0.90),
        PeakPercentile(0.95),
        PeakPercentile(1.00),
    ]


def walk_forward(book: Sequence[Day], policy: Policy, warmup: int = WARMUP) -> list[DayResult]:
    """Size every scored day from its own past, then release the day against it."""
    out = []
    for i in range(warmup, len(book)):
        out.append(simulate_day(book[i], policy.size(book[:i])))
    return out


def annualize(cents: int, days: int) -> float:
    if days == 0:
        return 0.0
    return round(cents * TRADING_DAYS / days / 100.0, 2)


def _row(name: str, results: list[DayResult], fee: int, emergency: float) -> dict:
    t = totals(results, fee_cents=fee, emergency_bps=emergency)
    worst = max((r.gap_cents for r in results), default=0)
    return {
        "policy": name,
        "mean_opening_usd": round(t["mean_opening_cents"] / 100.0, 2),
        "annual_total_usd": annualize(t["total_cents"], t["days"]),
        "annual_carry_usd": annualize(t["carry_cents"], t["days"]),
        "annual_fee_usd": annualize(t["fee_cents"], t["days"]),
        "annual_emergency_usd": annualize(t["emergency_cents"], t["days"]),
        "events": t["events"],
        "days_shorted": t["days_shorted"],
        "shortfall_rate": round(t["days_shorted"] / t["days"], 4) if t["days"] else 0.0,
        "worst_gap_usd": round(worst / 100.0, 2),
    }


def run_regime(label: str, note: str, params: BookParams, fee: int, emergency: float) -> dict:
    book = build_book(SEED, params)
    rows = [_row(p.name, walk_forward(book, p), fee, emergency) for p in policies()]
    required = [required_opening(d) for d in book[WARMUP:]]
    return {
        "regime": label,
        "note": note,
        "required_opening_p90_usd": round(sorted(required)[int(0.90 * len(required))] / 100.0, 2),
        "policies": rows,
    }


def run_bench(
    directory: Path | None = None,
    seed: int = SEED,
    fee_cents: int = DEFAULT_FEE_CENTS,
    emergency_bps: float = DEFAULT_EMERGENCY_BPS,
    carry_bps: float = CARRY_BPS_PER_DAY,
) -> dict:
    """Run everything and write results/. `directory=None` means the committed results dir."""
    out_dir = RESULTS if directory is None else Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_params = BookParams()
    book = build_book(seed, base_params)
    bt = book_totals(book)
    scored = book[WARMUP:]

    required = [required_opening(d) for d in scored]
    required_sorted = sorted(required)
    n = len(required_sorted)

    results_by_policy: dict[str, list[DayResult]] = {}
    rows = []
    for policy in policies():
        res = walk_forward(book, policy)
        results_by_policy[policy.name] = res
        rows.append(_row(policy.name, res, fee_cents, emergency_bps))

    oracle_results = [simulate_day(d, required_opening(d)) for d in scored]
    oracle_row = _row("oracle", oracle_results, fee_cents, emergency_bps)

    sweep = []
    for q in (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00):
        res = walk_forward(book, PeakPercentile(q))
        t = totals(res, fee_cents=fee_cents, emergency_bps=emergency_bps)
        sweep.append(
            {
                "q": q,
                "policy": PeakPercentile(q).name,
                "mean_opening_usd": round(t["mean_opening_cents"] / 100.0, 2),
                "annual_total_usd": annualize(t["total_cents"], t["days"]),
                "events": t["events"],
                "days_shorted": t["days_shorted"],
            }
        )

    windows = []
    for window in (20, 40, 80, 160):
        res = walk_forward(book, PeakPercentile(0.90, window=window))
        t = totals(res, fee_cents=fee_cents, emergency_bps=emergency_bps)
        windows.append(
            {
                "window": window,
                "mean_opening_usd": round(t["mean_opening_cents"] / 100.0, 2),
                "annual_total_usd": annualize(t["total_cents"], t["days"]),
                "events": t["events"],
                "days_shorted": t["days_shorted"],
            }
        )

    fee_rows = []
    for fee in (5_000, 25_000, 100_000):
        scored_rows = [
            (name, totals(res, fee_cents=fee, emergency_bps=emergency_bps))
            for name, res in results_by_policy.items()
        ]
        best_name, best_tot = min(scored_rows, key=lambda item: item[1]["total_cents"])
        fee_rows.append(
            {
                "fee_usd": fee / 100.0,
                "best_policy": best_name,
                "best_annual_usd": annualize(best_tot["total_cents"], best_tot["days"]),
                "peak_p90_usd": annualize(
                    totals(results_by_policy["peak_p90"], fee_cents=fee, emergency_bps=emergency_bps)["total_cents"],
                    len(results_by_policy["peak_p90"]),
                ),
                "peak_max_usd": annualize(
                    totals(results_by_policy["peak_p100"], fee_cents=fee, emergency_bps=emergency_bps)["total_cents"],
                    len(results_by_policy["peak_p100"]),
                ),
            }
        )

    regimes = [
        run_regime(
            "baseline",
            "4 percent of settlement days slip to the next morning",
            base_params,
            fee_cents,
            emergency_bps,
        ),
        run_regime(
            "slip 12 percent",
            "the acquirer delays three times as often",
            BookParams(slip_rate=0.12),
            fee_cents,
            emergency_bps,
        ),
        run_regime(
            "payout spikes 10 percent",
            "more merchants batch quarterly payouts through the same cutoff",
            BookParams(spike_rate=0.10),
            fee_cents,
            emergency_bps,
        ),
        run_regime(
            "batch one is 60 percent",
            "merchants move their cutoffs earlier in the day",
            BookParams(first_batch_share_mean=0.60),
            fee_cents,
            emergency_bps,
        ),
        run_regime(
            "settlement at the open",
            "the acquirer settles the whole day at 08:00, before any payout",
            BookParams(all_in_at_open=True),
            fee_cents,
            emergency_bps,
        ),
        run_regime(
            "volume steps up 25 percent",
            "a large merchant cohort goes live at business day 400",
            BookParams(jump_at=400, jump_mult=1.25),
            fee_cents,
            emergency_bps,
        ),
    ]

    retimed = next(r for r in regimes if r["regime"] == "settlement at the open")
    baseline = next(r for r in regimes if r["regime"] == "baseline")

    zero_res = results_by_policy["zero"]
    net_positive_days = sum(1 for d in scored if d.net_cents > 0)
    net_positive_shorted = sum(
        1 for d, r in zip(scored, zero_res) if d.net_cents > 0 and r.shorted
    )

    p90_result = next(r for r in rows if r["policy"] == "peak_p90")
    daily_p95 = next(r for r in rows if r["policy"] == "daily_net_p95")

    checks = {
        "every_eval_day_scored": all(len(r) == len(scored) for r in results_by_policy.values()),
        "oracle_has_no_shortfall": oracle_row["events"] == 0,
        "oracle_is_the_floor": all(
            oracle_row["annual_total_usd"] <= r["annual_total_usd"] for r in rows
        ),
        "every_net_positive_day_still_shorts_at_zero": net_positive_shorted == net_positive_days,
        "timing_policy_halves_the_daily_net_policy": p90_result["annual_total_usd"]
        < 0.5 * daily_p95["annual_total_usd"],
        "carry_rises_with_the_percentile": all(
            sweep[i]["mean_opening_usd"] <= sweep[i + 1]["mean_opening_usd"]
            for i in range(len(sweep) - 1)
        ),
        "retimed_settlement_needs_less_float": retimed["required_opening_p90_usd"]
        < baseline["required_opening_p90_usd"],
        "book_is_plausible": 100_000_000 <= bt["mean_payout_cents"] <= 300_000_000
        and abs(bt["net_cents"]) < 0.01 * bt["payout_cents"],
        "no_day_fails_more_than_two_batches": all(r.events <= 2 for res in results_by_policy.values() for r in res),
    }

    payload = {
        "seed": seed,
        "command": "PYTHONPATH=. uv run python -m liquidity.cli bench",
        "warmup_days": WARMUP,
        "eval_days": len(scored),
        "carry_bps_per_day": carry_bps,
        "fee_per_failed_batch_usd": fee_cents / 100.0,
        "emergency_bps": emergency_bps,
        "book": {
            "days": bt["days"],
            "payout_total_usd": round(bt["payout_cents"] / 100.0, 2),
            "mean_payout_usd": round(bt["mean_payout_cents"] / 100.0, 2),
            "net_total_usd": round(bt["net_cents"] / 100.0, 2),
            "net_positive_days": bt["net_positive_days"],
            "slipped_days": bt["slipped_days"],
        },
        "required_opening_usd": {
            "mean": round(sum(required) / n / 100.0, 2),
            "p50": round(required_sorted[n // 2] / 100.0, 2),
            "p90": round(required_sorted[int(0.90 * n)] / 100.0, 2),
            "p95": round(required_sorted[int(0.95 * n)] / 100.0, 2),
            "p99": round(required_sorted[int(0.99 * n)] / 100.0, 2),
            "max": round(required_sorted[-1] / 100.0, 2),
        },
        "policies": rows,
        "oracle": oracle_row,
        "sweep": sweep,
        "windows": windows,
        "fee_sensitivity": fee_rows,
        "regimes": regimes,
        "net_positive_days": net_positive_days,
        "net_positive_days_that_shorted": net_positive_shorted,
        "checks": checks,
    }

    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _money(value: float) -> str:
    return f"{value:,.0f}"


def render_markdown(p: dict) -> str:
    out = []
    out.append("# Intraday liquidity bench")
    out.append("")
    out.append(f"Seed {p['seed']}, {p['book']['days']} business days, {p['warmup_days']} burn in, {p['eval_days']} scored.")
    out.append(f"Payout volume USD {_money(p['book']['payout_total_usd'])}, net flow over the whole book USD {_money(p['book']['net_total_usd'])}.")
    out.append("")
    out.append("## Sizing policies")
    out.append("")
    table = [
        [
            r["policy"],
            _money(r["mean_opening_usd"]),
            _money(r["annual_total_usd"]),
            _money(r["annual_carry_usd"]),
            _money(r["annual_fee_usd"]),
            _money(r["annual_emergency_usd"]),
            str(r["events"]),
            f"{r['shortfall_rate'] * 100:.1f}%",
        ]
        for r in p["policies"]
    ]
    table.append(
        [
            "oracle",
            _money(p["oracle"]["mean_opening_usd"]),
            _money(p["oracle"]["annual_total_usd"]),
            _money(p["oracle"]["annual_carry_usd"]),
            _money(p["oracle"]["annual_fee_usd"]),
            _money(p["oracle"]["annual_emergency_usd"]),
            str(p["oracle"]["events"]),
            f"{p['oracle']['shortfall_rate'] * 100:.1f}%",
        ]
    )
    out.append(
        _md_table(
            [
                "policy",
                "mean opening USD",
                "annual cost USD",
                "of which carry",
                "of which fees",
                "of which facility",
                "failed batches",
                "days shorted",
            ],
            table,
        )
    )
    out.append("")
    out.append("## Percentile sweep")
    out.append("")
    out.append(
        _md_table(
            ["quantile", "mean opening USD", "annual cost USD", "failed batches", "days shorted"],
            [
                [
                    s["policy"],
                    _money(s["mean_opening_usd"]),
                    _money(s["annual_total_usd"]),
                    str(s["events"]),
                    str(s["days_shorted"]),
                ]
                for s in p["sweep"]
            ],
        )
    )
    out.append("")
    out.append("## Trailing window at the ninetieth percentile")
    out.append("")
    out.append(
        _md_table(
            ["window days", "mean opening USD", "annual cost USD", "failed batches", "days shorted"],
            [
                [
                    str(w["window"]),
                    _money(w["mean_opening_usd"]),
                    _money(w["annual_total_usd"]),
                    str(w["events"]),
                    str(w["days_shorted"]),
                ]
                for w in p["windows"]
            ],
        )
    )
    out.append("")
    out.append("## Fee sensitivity")
    out.append("")
    out.append(
        _md_table(
            ["fee per failed batch USD", "best policy", "best annual USD", "peak_p90 USD", "peak_p100 USD"],
            [
                [
                    _money(f["fee_usd"]),
                    f["best_policy"],
                    _money(f["best_annual_usd"]),
                    _money(f["peak_p90_usd"]),
                    _money(f["peak_max_usd"]),
                ]
                for f in p["fee_sensitivity"]
            ],
        )
    )
    out.append("")
    out.append("## Regimes")
    out.append("")
    for regime in p["regimes"]:
        out.append(f"### {regime['regime']}")
        out.append("")
        out.append(regime["note"])
        out.append("")
        rows = [
            [r["policy"], _money(r["mean_opening_usd"]), _money(r["annual_total_usd"]), str(r["events"])]
            for r in regime["policies"]
        ]
        out.append(_md_table(["policy", "mean opening USD", "annual cost USD", "failed batches"], rows))
        out.append("")
    out.append("## Checks")
    out.append("")
    for name, ok in p["checks"].items():
        out.append(f"- {name}: {'pass' if ok else 'FAIL'}")
    out.append("")
    return "\n".join(out)
