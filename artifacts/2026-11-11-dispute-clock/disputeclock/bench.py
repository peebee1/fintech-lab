"""Bench: one book, four policies, the same ceiling and the same budget."""

from __future__ import annotations

from . import engine, rules, sim
from .model import TERMINAL

LADDER = (
    engine.StatusOnly,
    engine.ResponseClock,
    engine.FreesAdded,
    engine.CompleteEvidence,
    engine.ThreeClock,
)


def _usd(minor: int) -> float:
    return round(minor / 100, 2)


def run(seed: int = 11, n: int = 2000, horizon: int = 360, budget: int = 40) -> dict:
    book = sim.build(seed=seed, n=n, horizon=horizon)
    results = [engine.run(book, policy(), budget_per_day=budget) for policy in LADDER]
    rows = [result.stats() for result in results]

    # The control has to bind: with analyst time no longer scarce, does the best
    # policy actually recover more? If not, the budget is decorative.
    unbounded = engine.run(book, engine.ThreeClock(), budget_per_day=100_000).stats()

    capacity = budget * (horizon + 1)
    total = book.total_minor
    checks = {
        "every_case_resolved": all(len(r.states) == len(book.cases) for r in results),
        "one_row_per_case": all(
            len({s.case.id for s in r.states}) == len(book.cases) for r in results
        ),
        "every_case_terminal": all(s.state in TERMINAL for r in results for s in r.states),
        "money_conserved": all(r.recovered_minor + r.lost_minor == total for r in results),
        "budget_binds": unbounded["recovered_usd"] > rows[-1]["recovered_usd"]
        and all(row["skipped_for_budget"] > 0 for row in rows),
        "deadline_binds": any(row["forfeited_cases"] > 0 for row in rows),
    }

    first, last = rows[0], rows[-1]
    payload = {
        "schema": "dispute-clock/1",
        "seed": seed,
        "horizon_days": horizon,
        "budget_minutes_per_day": budget,
        "budget_minutes_total": capacity,
        "book": {
            "cases": len(book.cases),
            "disputed_usd": _usd(total),
            "recoverable_usd": _usd(book.recoverable_minor),
            "recoverable_share": round(book.recoverable_minor / total, 4) if total else 0.0,
            "free_win_cases": sum(1 for c in book.cases if c.free_win),
            "free_win_usd": _usd(sum(c.amount_minor for c in book.cases if c.free_win)),
            "procedural_cases": sum(1 for c in book.cases if c.procedural_invalid),
            "liability_cases": sum(1 for c in book.cases if c.liability_shifted),
            "fraud_cases": sum(1 for c in book.cases if c.reason.is_fraud),
            "pre_arb_cases": sum(1 for c in book.cases if c.pre_arb),
            "window_20_cases": sum(
                1 for c in book.cases if rules.response_window(c) == 20
            ),
        },
        "policies": rows,
        "unbounded": unbounded,
        "deltas": {
            "clock_usd": round(rows[1]["recovered_usd"] - first["recovered_usd"], 2),
            "free_wins_usd": round(rows[2]["recovered_usd"] - rows[1]["recovered_usd"], 2),
            "evidence_gate_usd": round(rows[3]["recovered_usd"] - rows[2]["recovered_usd"], 2),
            "queue_and_pushback_usd": round(last["recovered_usd"] - rows[3]["recovered_usd"], 2),
            "scarcity_usd": round(unbounded["recovered_usd"] - last["recovered_usd"], 2),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    return payload


def summary_text(payload: dict) -> str:
    b = payload["book"]
    lines = [
        f"book          {b['cases']} disputes, ${b['disputed_usd']:,.2f} disputed",
        f"ceiling       ${b['recoverable_usd']:,.2f} defensible ({b['recoverable_share']:.1%} of value)",
        f"free wins     {b['free_win_cases']} cases, ${b['free_win_usd']:,.2f}"
        f" (procedural {b['procedural_cases']}, liability {b['liability_cases']})",
        f"budget        {payload['budget_minutes_per_day']} min/day,"
        f" {payload['budget_minutes_total']:,} min over {payload['horizon_days']} days",
        "",
        f"{'policy':<18}{'recovered':>12}{'rate':>8}{'forfeit':>9}{'fought':>8}{'prec':>7}"
        f"{'min':>7}{'waste':>7}",
    ]
    for row in payload["policies"]:
        lines.append(
            f"{row['policy']:<18}{row['recovered_usd']:>12,.2f}{row['recovery_rate']:>7.1%}"
            f"{row['forfeited_cases']:>9}{row['contested']:>8}{row['contest_precision']:>7.2f}"
            f"{row['minutes']:>7}{row['wasted_minutes']:>7}"
        )
    u = payload["unbounded"]
    d = payload["deltas"]
    lines += [
        f"{'unlimited time':<18}{u['recovered_usd']:>12,.2f}{u['recovery_rate']:>7.1%}"
        f"{u['forfeited_cases']:>9}{u['contested']:>8}{u['contest_precision']:>7.2f}"
        f"{u['minutes']:>7}{u['wasted_minutes']:>7}",
        "",
        f"clock modelled       +${d['clock_usd']:,.2f}",
        f"free wins added      +${d['free_wins_usd']:,.2f}",
        f"evidence gate added  +${d['evidence_gate_usd']:,.2f}",
        f"queue and pushback   +${d['queue_and_pushback_usd']:,.2f}",
        f"one analyst costs    ${d['scarcity_usd']:,.2f} of that",
        "",
        "checks: "
        + ", ".join(f"{name}={'ok' if ok else 'FAIL'}" for name, ok in payload["checks"].items()),
    ]
    return "\n".join(lines)
