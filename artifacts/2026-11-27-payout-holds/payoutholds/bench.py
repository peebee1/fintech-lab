"""The bench: every policy on one book, the sweeps, and the numbers the README quotes."""

from __future__ import annotations

import json
from pathlib import Path

from .book import Book, generate
from .ledger import simulate, simulate_oracle
from .policies import HOLD_SWEEP, LADDER, RESERVE_SWEEP, Policy

RESULTS = Path(__file__).resolve().parents[1] / "results"


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def _lean(result: dict) -> dict:
    out = dict(result)
    out.pop("rows", None)
    return out


def _sweep_reserve(book: Book) -> list[dict]:
    return [
        _lean(simulate(Policy(f"reserve_{int(rate * 100)}", reserve_rate=rate, reserve_days=30), book))
        for rate in RESERVE_SWEEP
    ]


def _sweep_hold(book: Book) -> list[dict]:
    return [
        _lean(simulate(Policy(f"hold_{days}", hold_days=days), book)) for days in HOLD_SWEEP
    ]


def _robustness(seeds: list[int] | None = None) -> list[dict]:
    """The same three claims on other books, so the finding is not one seed's story."""
    rows = []
    for seed in seeds or [20261128, 20261129]:
        other = generate(seed=seed)
        base = simulate(Policy("pay_t1", hold_days=1), other)
        tiered = simulate(Policy("tiered_hold", tiered=True), other)
        oracle = simulate_oracle(other)
        flat = [
            _lean(
                simulate(
                    Policy(f"reserve_{int(rate * 100)}", reserve_rate=rate, reserve_days=30), other
                )
            )
            for rate in (0.10, 0.15, 0.20)
        ]
        best = min(flat, key=lambda r: r["totals"]["economic_cost_cents"])
        prize = (
            base["totals"]["economic_cost_cents"] - oracle["totals"]["economic_cost_cents"]
        )
        rows.append(
            {
                "seed": seed,
                "gmv_cents": other.gmv_cents,
                "base_economic_cents": base["totals"]["economic_cost_cents"],
                "base_writeoff_cents": base["totals"]["written_off"],
                "best_flat_policy": best["policy"]["name"],
                "best_flat_writeoff_cents": best["totals"]["written_off"],
                "best_flat_economic_cents": best["totals"]["economic_cost_cents"],
                "tiered_hold_economic_cents": tiered["totals"]["economic_cost_cents"],
                "oracle_economic_cents": oracle["totals"]["economic_cost_cents"],
                "prize_captured_pct": 100.0
                * (
                    base["totals"]["economic_cost_cents"]
                    - best["totals"]["economic_cost_cents"]
                )
                / (prize or 1),
            }
        )
    return rows


def build(seed: int = 20261127, sellers: int = 400, days: int = 180) -> dict:
    book = generate(seed=seed, sellers=sellers, days=days)
    results = {policy.name: simulate(policy, book) for policy in LADDER}
    oracle = simulate_oracle(book)
    reserve_sweep = _sweep_reserve(book)
    hold_sweep = _sweep_hold(book)
    robustness = _robustness()

    ladder = {name: _lean(result) for name, result in results.items()}
    base = results["pay_t1"]
    tiered = results["tiered_hold"]
    best_flat = min(reserve_sweep, key=lambda r: r["totals"]["economic_cost_cents"])

    marginal = []
    for low, high in zip(reserve_sweep, reserve_sweep[1:]):
        saved = low["totals"]["written_off"] - high["totals"]["written_off"]
        cost = high["totals"]["float_cost_cents"] - low["totals"]["float_cost_cents"]
        marginal.append(
            {
                "from_rate": low["policy"]["reserve_rate"],
                "to_rate": high["policy"]["reserve_rate"],
                "writeoff_saved_cents": saved,
                "float_added_cents": cost,
                "net_cents": saved - cost,
            }
        )

    hold = results["hold_14"]
    prize = base["totals"]["economic_cost_cents"] - oracle["totals"]["economic_cost_cents"]
    comparisons = {
        "writeoff_cut_base_to_reserve_10_pct": 100.0
        * (base["totals"]["written_off"] - results["reserve_10"]["totals"]["written_off"])
        / (base["totals"]["written_off"] or 1),
        "best_flat_policy": best_flat["policy"]["name"],
        "best_flat_rate_pct": 100 * best_flat["policy"]["reserve_rate"],
        "best_flat_economic_cents": best_flat["totals"]["economic_cost_cents"],
        "best_flat_writeoff_cents": best_flat["totals"]["written_off"],
        "best_flat_float_cents": best_flat["totals"]["float_cost_cents"],
        "tiered_economic_cents": tiered["totals"]["economic_cost_cents"],
        "tiered_writeoff_cents": tiered["totals"]["written_off"],
        "tiered_float_cents": tiered["totals"]["float_cost_cents"],
        "tiered_vs_best_flat_cents": tiered["totals"]["economic_cost_cents"]
        - best_flat["totals"]["economic_cost_cents"],
        "tiered_reserve_economic_cents": results["tiered_reserve"]["totals"]["economic_cost_cents"],
        "tiered_reserve_vs_best_flat_cents": results["tiered_reserve"]["totals"]["economic_cost_cents"]
        - best_flat["totals"]["economic_cost_cents"],
        "hold14_writeoff_cents": hold["totals"]["written_off"],
        "hold14_float_cents": hold["totals"]["float_cost_cents"],
        "reserve_10_writeoff_cents": results["reserve_10"]["totals"]["written_off"],
        "reserve_10_float_cents": results["reserve_10"]["totals"]["float_cost_cents"],
        "clawback_value_cents": results["reserve_10_no_clawback"]["totals"]["written_off"]
        - results["reserve_10"]["totals"]["written_off"],
        "oracle_writeoff_cents": oracle["totals"]["written_off"],
        "oracle_economic_cents": oracle["totals"]["economic_cost_cents"],
        "prize_cents": prize,
        "prize_captured_pct": 100.0
        * (base["totals"]["economic_cost_cents"] - best_flat["totals"]["economic_cost_cents"])
        / (prize or 1),
        "best_policy": min(ladder, key=lambda name: ladder[name]["totals"]["economic_cost_cents"]),
    }

    sweeps_monotone = all(
        low["totals"]["written_off"] >= high["totals"]["written_off"]
        for low, high in zip(reserve_sweep, reserve_sweep[1:])
    )
    economics = [row["totals"]["economic_cost_cents"] for row in reserve_sweep]
    turn_index = economics.index(min(economics))

    policy_checks = {name: all(result["checks"].values()) for name, result in results.items()}
    checks = {
        **{f"{name}_balances": ok for name, ok in policy_checks.items()},
        "oracle_never_writes_off": oracle["totals"]["written_off"] == 0,
        "zero_reserve_binds": base["totals"]["written_off"] > 0,
        "reserve_reduces_writeoff": results["reserve_10"]["totals"]["written_off"]
        < base["totals"]["written_off"],
        "reserve_sweep_is_monotone": sweeps_monotone,
        "reserve_curve_turns": 0 < turn_index < len(reserve_sweep) - 1,
        "the_best_flat_rung_is_stable_across_seeds": all(
            row["best_flat_policy"] == best_flat["policy"]["name"] for row in robustness
        ),
        "reserve_dominates_hold": results["reserve_10"]["totals"]["written_off"]
        < hold["totals"]["written_off"]
        and results["reserve_10"]["totals"]["float_cost_cents"] < hold["totals"]["float_cost_cents"],
        "clawback_carries_the_reserve": comparisons["clawback_value_cents"] > 0,
        "tiered_beats_base": tiered["totals"]["economic_cost_cents"]
        < base["totals"]["economic_cost_cents"],
        "oracle_is_the_floor": min(r["totals"]["economic_cost_cents"] for r in ladder.values())
        >= oracle["totals"]["economic_cost_cents"],
    }

    return {
        "book": {
            "seed": book.seed,
            "days": book.days,
            "sellers": len(book.sellers),
            "orders": len(book.orders),
            "refunds": len(book.refunds),
            "gmv_cents": book.gmv_cents,
            "refund_cost_cents": book.refund_cost_cents,
            "horizon_days": book.horizon,
            "digest": book.digest(),
        },
        "policies": ladder,
        "oracle": _lean(oracle),
        "sweeps": {"reserve": reserve_sweep, "hold": hold_sweep},
        "robustness": robustness,
        "marginal_reserve": marginal,
        "comparisons": comparisons,
        "checks": checks,
    }


def render_markdown(summary: dict) -> str:
    book = summary["book"]
    policies = summary["policies"]
    comp = summary["comparisons"]
    lines = [
        "# Seller payout bench",
        "",
        f"Synthetic book, seed {book['seed']}, {book['days']} days, {book['sellers']} sellers, "
        f"{book['orders']:,} orders, {book['refunds']:,} refunds, {usd(book['gmv_cents'])} GMV, "
        f"refund cost {usd(book['refund_cost_cents'])}.",
        "",
        "| Policy | Hold | Reserve | Write-off | Float cost | Economic | Write-off bps | Economic bps | Sellers written off |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, result in policies.items():
        policy = result["policy"]
        hold = "banded" if policy["tiered"] else str(policy["hold_days"])
        reserve = (
            f"{pct(policy['reserve_rate'] * 100)}% / {policy['reserve_days']}d"
            if policy["reserve_rate"]
            else ("banded" if policy["tiered"] else "none")
        )
        totals = result["totals"]
        lines.append(
            f"| {name} | {hold} | {reserve} | {usd(totals['written_off'])} | "
            f"{usd(totals['float_cost_cents'])} | {usd(totals['economic_cost_cents'])} | "
            f"{pct(result['rates']['written_off_bps'], 2)} | {pct(result['rates']['economic_bps'], 2)} | "
            f"{result['writeoff']['sellers']} |"
        )
    oracle = summary["oracle"]
    lines.append(
        f"| oracle | exact | exact | {usd(oracle['totals']['written_off'])} | "
        f"{usd(oracle['totals']['float_cost_cents'])} | {usd(oracle['totals']['economic_cost_cents'])} | "
        f"{pct(oracle['rates']['written_off_bps'], 2)} | {pct(oracle['rates']['economic_bps'], 2)} | 0 |"
    )

    lines += [
        "",
        "## Reserve sweep at a one day payout",
        "",
        "| Reserve rate | Reserve days | Write-off | Float cost | Economic | Write-off bps |",
        "|---|---|---|---|---|---|",
    ]
    for row in summary["sweeps"]["reserve"]:
        policy = row["policy"]
        totals = row["totals"]
        lines.append(
            f"| {pct(policy['reserve_rate'] * 100)}% | {policy['reserve_days']} | "
            f"{usd(totals['written_off'])} | {usd(totals['float_cost_cents'])} | "
            f"{usd(totals['economic_cost_cents'])} | {pct(row['rates']['written_off_bps'], 2)} |"
        )

    lines += [
        "",
        "## Marginal return per five points of reserve",
        "",
        "| From | To | Write-off saved | Float added | Net |",
        "|---|---|---|---|---|",
    ]
    for rung in summary["marginal_reserve"]:
        lines.append(
            f"| {pct(rung['from_rate'] * 100)}% | {pct(rung['to_rate'] * 100)}% | "
            f"{usd(rung['writeoff_saved_cents'])} | {usd(rung['float_added_cents'])} | "
            f"{usd(rung['net_cents'])} |"
        )

    lines += [
        "",
        "## Hold sweep at zero reserve",
        "",
        "| Hold days | Write-off | Float cost | Economic | Write-off bps |",
        "|---|---|---|---|---|",
    ]
    for row in summary["sweeps"]["hold"]:
        totals = row["totals"]
        lines.append(
            f"| {row['policy']['hold_days']} | {usd(totals['written_off'])} | "
            f"{usd(totals['float_cost_cents'])} | {usd(totals['economic_cost_cents'])} | "
            f"{pct(row['rates']['written_off_bps'], 2)} |"
        )

    lines += [
        "",
        "## The same claims on other books",
        "",
        "| Seed | GMV | Pay T+1 write-off | Pay T+1 economic | Best flat | Best flat economic | Tiered hold economic | Oracle | Prize captured |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| {book['seed']} | {usd(book['gmv_cents'])} | {usd(policies['pay_t1']['totals']['written_off'])} | "
        f"{usd(policies['pay_t1']['totals']['economic_cost_cents'])} | {comp['best_flat_policy']} | "
        f"{usd(comp['best_flat_economic_cents'])} | {usd(comp['tiered_economic_cents'])} | "
        f"{usd(comp['oracle_economic_cents'])} | {pct(comp['prize_captured_pct'])}% |",
    ]
    for row in summary["robustness"]:
        lines.append(
            f"| {row['seed']} | {usd(row['gmv_cents'])} | {usd(row['base_writeoff_cents'])} | "
            f"{usd(row['base_economic_cents'])} | {row['best_flat_policy']} | "
            f"{usd(row['best_flat_economic_cents'])} | {usd(row['tiered_hold_economic_cents'])} | "
            f"{usd(row['oracle_economic_cents'])} | {pct(row['prize_captured_pct'])}% |"
        )

    lines += [
        "",
        "## Comparison",
        "",
        f"- Zero reserve write-off is {usd(policies['pay_t1']['totals']['written_off'])}. "
        f"A 10 percent reserve cuts it {pct(comp['writeoff_cut_base_to_reserve_10_pct'])} percent.",
        f"- The best flat rung is {comp['best_flat_policy']} at "
        f"{usd(comp['best_flat_economic_cents'])}, writing off "
        f"{usd(comp['best_flat_writeoff_cents'])} for {usd(comp['best_flat_float_cents'])} of float.",
        f"- The banded hold policy costs {usd(comp['tiered_economic_cents'])}, "
        f"{usd(abs(comp['tiered_vs_best_flat_cents']))} "
        f"{'more' if comp['tiered_vs_best_flat_cents'] > 0 else 'less'} than the best flat rung. "
        f"The banded reserve policy costs {usd(comp['tiered_reserve_economic_cents'])}, "
        f"{usd(abs(comp['tiered_reserve_vs_best_flat_cents']))} "
        f"{'more' if comp['tiered_reserve_vs_best_flat_cents'] > 0 else 'less'}.",
        f"- A 14 day hold writes off {usd(comp['hold14_writeoff_cents'])} for "
        f"{usd(comp['hold14_float_cents'])} of float; a 10 percent reserve writes off "
        f"{usd(comp['reserve_10_writeoff_cents'])} for {usd(comp['reserve_10_float_cents'])}.",
        f"- Clawback from later payouts is worth {usd(comp['clawback_value_cents'])} of write-off "
        "at the same reserve rate.",
        f"- The oracle writes off {usd(comp['oracle_writeoff_cents'])} at "
        f"{usd(comp['oracle_economic_cents'])}, prize {usd(comp['prize_cents'])}, and the best "
        f"flat rung captures {pct(comp['prize_captured_pct'])} percent of it.",
    ]

    failed = [name for name, ok in summary["checks"].items() if not ok]
    lines += ["", "## Checks", ""]
    lines.append("All checks pass." if not failed else "Failed: " + ", ".join(failed))
    return "\n".join(lines)


def summary_lines(summary: dict) -> list[str]:
    book = summary["book"]
    policies = summary["policies"]
    comp = summary["comparisons"]
    return [
        f"book: {book['orders']:,} orders, {usd(book['gmv_cents'])} GMV, "
        f"{book['refunds']:,} refunds, digest {book['digest']}",
        f"pay_t1: {usd(policies['pay_t1']['totals']['written_off'])} written off, "
        f"economic {usd(policies['pay_t1']['totals']['economic_cost_cents'])}",
        f"{comp['best_flat_policy']}: {usd(comp['best_flat_writeoff_cents'])} written off, "
        f"economic {usd(comp['best_flat_economic_cents'])}, float {usd(comp['best_flat_float_cents'])}",
        f"tiered_hold: {usd(comp['tiered_writeoff_cents'])} written off, "
        f"economic {usd(comp['tiered_economic_cents'])}",
        f"oracle: {usd(comp['oracle_economic_cents'])}, best flat captures "
        f"{pct(comp['prize_captured_pct'])} percent of the prize",
    ]


def write_results(directory: Path | None = None, summary: dict | None = None) -> Path:
    target = RESULTS if directory is None else Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    payload = build() if summary is None else summary
    (target / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (target / "summary.md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return target
