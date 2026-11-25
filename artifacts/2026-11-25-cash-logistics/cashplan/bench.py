"""The bench: replay every policy, price it, and write the numbers the README quotes."""

from __future__ import annotations

import json
from pathlib import Path

from .book import NOTE_PAISE, generate
from .policies import BY_NAME, POLICIES, PRACTICAL
from .sim import (
    EMERGENCY_VISIT_PAISE,
    HANDLING_PAISE_PER_NOTE,
    LOST_WITHDRAWAL_PAISE,
    RATE_BPS,
    VISIT_PAISE,
    Result,
    run,
    sweep_capacity,
)

RESULTS = Path(__file__).resolve().parents[1] / "results"
SERVICE_TARGET = 0.995
HEADLINE_POLICY = "minmax_3_6"


def inr(paise: int) -> str:
    return f"INR {paise / 100:,.2f}"


def bps(paise: int, value_paise: int) -> float:
    return 0.0 if value_paise == 0 else round(paise * 10_000 / value_paise, 2)


def _result_row(result: Result) -> dict:
    return {
        "policy": result.policy,
        "visits": result.visits,
        "emergency_visits": result.emergency_visits,
        "delivered_notes": result.delivered,
        "dispensed_notes": result.dispensed,
        "lost_notes": result.lost_notes,
        "withdrawals": result.withdrawals,
        "served_withdrawals": result.served,
        "lost_withdrawals": result.lost_withdrawals,
        "service_level": round(result.service_level, 6),
        "stockout_site_days": result.stockout_days,
        "mean_balance_notes": round(result.mean_balance_notes, 1),
        "cit_paise": result.cit_paise,
        "capital_paise": result.capital_paise,
        "lost_paise": result.lost_paise,
        "total_paise": result.total_paise,
    }


def _comparisons(book, results, cheapest, weekly, oracle, sweep_fixed, value_paise) -> dict:
    """Every ratio the README quotes, computed here so no number is hand typed."""
    by_name = {r.policy: r for r in results}
    fortnight = by_name["fixed_fortnight_cover"]
    trimmed = by_name["fixed_week_cover"]
    best = cheapest
    gap = best.total_paise - oracle.total_paise
    compliant_rungs = [row for row in sweep_fixed if row["service_level"] >= SERVICE_TARGET]
    first_compliant = compliant_rungs[0] if compliant_rungs else None
    metro_lost = next((row["lost_withdrawals"] for row in weekly.by_kind() if row["kind"] == "metro"), 0)

    def pct(numerator: int, denominator: int) -> float:
        return 0.0 if denominator == 0 else round(numerator * 100.0 / denominator, 2)

    return {
        "weekly_extra_paise": weekly.total_paise - best.total_paise,
        "weekly_extra_pct_of_best": pct(weekly.total_paise - best.total_paise, best.total_paise),
        "weekly_capital_extra_paise": weekly.capital_paise - best.capital_paise,
        "weekly_cit_saved_paise": best.cit_paise - weekly.cit_paise,
        "weekly_service_gap_points": round((best.service_level - weekly.service_level) * 100, 3),
        "best_visit_delta_vs_weekly": best.visits - weekly.visits,
        "best_balance_delta_notes": round(best.mean_balance_notes - weekly.mean_balance_notes, 1),
        "trim_capital_saved_paise": weekly.capital_paise - trimmed.capital_paise,
        "trim_lost_added_paise": trimmed.lost_paise - weekly.lost_paise,
        "trim_net_paise": trimmed.total_paise - weekly.total_paise,
        "trim_service_drop_points": round((weekly.service_level - trimmed.service_level) * 100, 3),
        "trim_lost_withdrawals": trimmed.lost_withdrawals,
        "fortnight_cit_pct_below_best": pct(best.cit_paise - fortnight.cit_paise, best.cit_paise),
        "fortnight_total_pct_above_best": pct(fortnight.total_paise - best.total_paise, best.total_paise),
        "fortnight_lost_share_pct": pct(fortnight.lost_withdrawals, fortnight.withdrawals),
        "fortnight_trips_vs_weekly": weekly.visits - fortnight.visits,
        "calendar_extra_paise": by_name["calendar_two_runs"].total_paise - best.total_paise,
        "calendar_extra_pct_of_best": pct(
            by_name["calendar_two_runs"].total_paise - best.total_paise, best.total_paise
        ),
        "calendar_lost_withdrawals": by_name["calendar_two_runs"].lost_withdrawals,
        "oracle_gap_pct_of_best": pct(gap, best.total_paise),
        "oracle_visit_delta_vs_best": oracle.visits - best.visits,
        "oracle_balance_delta_notes": round(oracle.mean_balance_notes - best.mean_balance_notes, 1),
        "oracle_cit_delta_paise": oracle.cit_paise - best.cit_paise,
        "oracle_capital_delta_paise": oracle.capital_paise - best.capital_paise,
        "best_bps_of_value": bps(best.total_paise, value_paise),
        "weekly_bps_of_value": bps(weekly.total_paise, value_paise),
        "oracle_bps_of_value": bps(oracle.total_paise, value_paise),
        "fixed_first_compliant_rung": None if first_compliant is None else first_compliant["cassettes"],
        "fixed_first_compliant_paise": None if first_compliant is None else first_compliant["total_paise"],
        "fixed_compliant_pct_above_best": None
        if first_compliant is None
        else pct(first_compliant["total_paise"] - best.total_paise, best.total_paise),
        "metro_share_of_weekly_lost_pct": pct(metro_lost, weekly.lost_withdrawals),
        "metro_lost_withdrawals": metro_lost,
        "weekly_stockout_site_days": weekly.stockout_days,
        "sites": len(book.sites),
    }


def build(seed: int = 20261125, days: int = 120) -> dict:
    book = generate(seed=seed, days=days)
    results = [run(book, policy) for policy in POLICIES]
    practical = [r for r in results if r.policy in {p.name for p in PRACTICAL}]
    cheapest = min(practical, key=lambda r: r.total_paise)
    compliant = [r for r in practical if r.service_level >= SERVICE_TARGET]
    best_compliant = min(compliant, key=lambda r: r.total_paise) if compliant else None
    oracle = next(r for r in results if r.policy == "oracle_minmax")
    headline = next(r for r in results if r.policy == HEADLINE_POLICY)
    weekly = next(r for r in results if r.policy == "fixed_week_capacity")
    sweep_headline = sweep_capacity(book, BY_NAME[HEADLINE_POLICY])
    sweep_fixed = sweep_capacity(book, BY_NAME["fixed_week_capacity"])

    value_paise = book.notes_dispensed() * NOTE_PAISE
    summary = {
        "book": {
            "seed": book.seed,
            "days": book.days,
            "sites": len(book.sites),
            "sites_by_kind": {kind: check for kind, check in _kind_counts(book)},
            "withdrawals": book.withdrawals(),
            "notes": book.notes_dispensed(),
            "value_paise": value_paise,
            "note_paise": NOTE_PAISE,
        },
        "tariff": {
            "rate_bps": RATE_BPS,
            "visit_paise": VISIT_PAISE,
            "emergency_visit_paise": EMERGENCY_VISIT_PAISE,
            "handling_paise_per_note": HANDLING_PAISE_PER_NOTE,
            "lost_withdrawal_paise": LOST_WITHDRAWAL_PAISE,
        },
        "policies": [_result_row(r) for r in results],
        "cheapest_practical": cheapest.policy,
        "best_compliant": best_compliant.policy if best_compliant else None,
        "service_target": SERVICE_TARGET,
        "service_premium_paise": None
        if best_compliant is None
        else best_compliant.total_paise - cheapest.total_paise,
        "oracle_gap_paise": cheapest.total_paise - oracle.total_paise,
        "comparisons": _comparisons(book, results, cheapest, weekly, oracle, sweep_fixed, value_paise),
        "headline_by_kind": headline.by_kind(),
        "weekly_by_kind": weekly.by_kind(),
        "capacity_sweep_headline": sweep_headline,
        "capacity_sweep_fixed": sweep_fixed,
        "checks": _checks(
            book, results, value_paise, cheapest, best_compliant, sweep_headline, sweep_fixed, seed, days
        ),
    }
    return summary


def _kind_counts(book) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for site in book.sites:
        counts[site.kind] = counts.get(site.kind, 0) + 1
    return sorted(counts.items())


def _checks(book, results, value_paise, cheapest, best_compliant, sweep_headline, sweep_fixed, seed, days) -> dict:
    again = generate(seed=seed, days=days)
    bounds = all(not r.violations for r in results)
    control = (
        any(r.cit_paise > 0 for r in results)
        and any(r.capital_paise > 0 for r in results)
        and any(r.lost_paise > 0 for r in results)
        and any(r.lost_paise == 0 for r in results)
    )
    partition = all(
        r.cit_paise + r.capital_paise + r.lost_paise == r.total_paise for r in results
    )
    service_gap = any(r.service_level < SERVICE_TARGET for r in results)
    oracle = next(r for r in results if r.policy == "oracle_minmax")
    return {
        "conservation_and_capacity": bounds,
        "cost_partition": partition,
        "book_rebuilds_identically": again.notes_dispensed() == book.notes_dispensed()
        and again.withdrawals() == book.withdrawals(),
        "control_binds": control,
        "some_policy_misses_target": service_gap,
        "target_has_a_policy": best_compliant is not None,
        "oracle_at_least_as_cheap": oracle.total_paise <= cheapest.total_paise,
        "sweep_covers_every_rung": len(sweep_headline) == 5 and len(sweep_fixed) == 5,
        "value_paise_reconciles": value_paise == book.notes_dispensed() * NOTE_PAISE,
    }


def render_markdown(summary: dict) -> str:
    book = summary["book"]
    lines = [
        "# Cash logistics bench",
        "",
        f"Synthetic network, seed {book['seed']}, {book['days']} days, {book['sites']} machines, "
        f"{book['notes']:,} notes dispensed ({inr(book['value_paise'])}).",
        "",
        "| Policy | Trips | Emergency | Service | Held notes | CIT | Capital | Lost | Total |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["policies"]:
        lines.append(
            f"| {row['policy']} | {row['visits']} | {row['emergency_visits']} | "
            f"{row['service_level'] * 100:.3f}% | {row['mean_balance_notes']:,.1f} | "
            f"{inr(row['cit_paise'])} | {inr(row['capital_paise'])} | {inr(row['lost_paise'])} | "
            f"{inr(row['total_paise'])} |"
        )
    lines += ["", "Capacity sweep on fixed_week_capacity: cadence held at one trip a week, machines resized.", ""]
    lines += ["| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |"]
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in summary["capacity_sweep_fixed"]:
        lines.append(
            f"| {row['cassettes']} | {row['capacity_notes']:,} | {row['visits']} | "
            f"{row['service_level'] * 100:.3f}% | {inr(row['cit_paise'])} | {inr(row['capital_paise'])} | "
            f"{inr(row['lost_paise'])} | {inr(row['total_paise'])} |"
        )
    lines += ["", "Capacity sweep on " + HEADLINE_POLICY + ": any day trips allowed, machines resized.", ""]
    lines += ["| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |"]
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in summary["capacity_sweep_headline"]:
        lines.append(
            f"| {row['cassettes']} | {row['capacity_notes']:,} | {row['visits']} | "
            f"{row['service_level'] * 100:.3f}% | {inr(row['cit_paise'])} | {inr(row['capital_paise'])} | "
            f"{inr(row['lost_paise'])} | {inr(row['total_paise'])} |"
        )
    return "\n".join(lines)


def summary_lines(summary: dict) -> list[str]:
    book = summary["book"]
    by_name = {row["policy"]: row for row in summary["policies"]}
    cheapest = by_name[summary["cheapest_practical"]]
    oracle = by_name["oracle_minmax"]
    lines = [
        f"book: {book['sites']} sites, {book['days']} days, {book['notes']:,} notes, {inr(book['value_paise'])}",
        f"cheapest practical: {cheapest['policy']} {inr(cheapest['total_paise'])} "
        f"service {cheapest['service_level'] * 100:.3f}%",
        f"oracle: {inr(oracle['total_paise'])}, gap {inr(summary['oracle_gap_paise'])}",
    ]
    if summary["best_compliant"]:
        row = by_name[summary["best_compliant"]]
        lines.append(
            f"service {summary['service_target'] * 100:.1f}% met by {row['policy']} at {inr(row['total_paise'])}, "
            f"premium {inr(summary['service_premium_paise'])}"
        )
    else:
        lines.append(f"no policy meets the {summary['service_target'] * 100:.1f}% service target")
    return lines


def write_results(directory: Path | None = None, summary: dict | None = None) -> Path:
    """Write summary.json and summary.md.

    The default is resolved here rather than bound at import, so a test that
    points the writer at a scratch directory really writes there.
    """
    target = RESULTS if directory is None else directory
    target.mkdir(parents=True, exist_ok=True)
    payload = build() if summary is None else summary
    (target / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (target / "summary.md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return target
