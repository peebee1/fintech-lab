"""Bench: one session, three policies, one detector scored against ground truth."""

from __future__ import annotations

import random

from . import metrics, recon, sim
from .model import Break, Session


def _residual(session: Session, positions: dict[str, int], truth: dict[str, int]) -> tuple[int, float]:
    shares = 0
    rupees = 0.0
    for symbol in session.symbols:
        gap = positions.get(symbol, 0) - truth.get(symbol, 0)
        shares += abs(gap)
        rupees += abs(gap) * session.last_price.get(symbol, 0) / 100
    return shares, round(rupees, 2)


def _row(
    name: str,
    session: Session,
    truth_pos: dict[str, int],
    truth_cash: int,
    positions: dict[str, int],
    cash: int | None,
    breaks: list[Break],
) -> dict:
    shares, rupees = _residual(session, positions, truth_pos)
    scored = metrics.score(session.truth, breaks)
    return {
        "policy": name,
        "breaks_detected": len(breaks),
        "precision": scored["precision"],
        "recall": scored["recall"],
        "f1": scored["f1"],
        "position_gap_shares": shares,
        "position_gap_rupees": rupees,
        "cash_gap_rupees": None if cash is None else round((cash - truth_cash) / 100, 2),
    }


def run(seed: int = 11, n_orders: int = 1200, per_class: int = 40, budget: int = 60) -> dict:
    session = sim.build(seed=seed, n_orders=n_orders, per_class=per_class)
    truth_pos = recon.tape_positions(session)
    truth_cash = recon.tape_cash(session)

    broker_pos = recon.broker_positions(session)
    app_pos, broker_app_breaks = recon.broker_vs_app(session)
    stream_pos, stream_cash, stream_breaks = recon.stream_positions(session)
    three_pos, three_cash, three_breaks = recon.tape_three_way(session)

    rows = [
        _row("broker_only", session, truth_pos, truth_cash, broker_pos, None, []),
        _row("broker_vs_app", session, truth_pos, truth_cash, app_pos, None, broker_app_breaks),
        _row("stream_replay", session, truth_pos, truth_cash, stream_pos, stream_cash, stream_breaks),
        _row("tape_three_way", session, truth_pos, truth_cash, three_pos, three_cash, three_breaks),
    ]

    scored = metrics.score(session.truth, three_breaks)
    triage = metrics.triage(three_breaks, budget=budget, rng=random.Random(seed + 1))

    explained = recon.explain(session, three_breaks)
    phantom_symbols = {row["key"] for row in session.truth if row["class"] == "phantom_position"}
    gaps = []
    flipped = []
    for symbol in session.symbols:
        if symbol in phantom_symbols:
            continue
        delta = explained.get(symbol, 0)
        gaps.append(session.app_positions[symbol] + delta - truth_pos[symbol])
        flipped.append(session.app_positions[symbol] - delta - truth_pos[symbol])
    cash_gap = session.app_cash + recon.cash_explained(session, three_breaks) - truth_cash

    orders_with_breaks = {brk.key for brk in three_breaks if brk.cls != "phantom_position"}

    payload = {
        "config": {
            "seed": seed,
            "orders": n_orders,
            "per_class": per_class,
            "review_budget": budget,
            "symbols": list(session.symbols),
        },
        "session": {
            "fills": len(session.tape),
            "orders_with_fills": len({fill.order_id for fill in session.tape}),
            "app_fills": len(session.app_fills),
            "injected_breaks": len(session.truth),
            "orders_flagged": len(orders_with_breaks),
        },
        "policies": rows,
        "classes": scored["per_class"],
        "invariants": {
            "symbols_checked": len(gaps),
            "max_share_gap": max((abs(g) for g in gaps), default=0),
            "max_share_gap_with_flipped_sign": max((abs(g) for g in flipped), default=0),
            "cash_gap_paise": cash_gap,
            "total_explained_shares": sum(abs(v) for v in explained.values()),
        },
        "triage": triage,
    }
    return payload


def _money(paise: int) -> str:
    return f"{paise / 100:,.0f}"


def summary_text(payload: dict) -> str:
    lines = []
    cfg = payload["config"]
    ses = payload["session"]
    lines.append(
        f"session: {ses['fills']} prints, {ses['orders_with_fills']} orders with fills, "
        f"{ses['injected_breaks']} injected breaks, {ses['orders_flagged']} orders flagged"
    )
    lines.append("")
    header = f"{'policy':<16}{'breaks':>7}{'prec':>7}{'recall':>7}{'gap sh':>9}{'gap INR':>12}{'cash INR':>11}"
    lines.append(header)
    for row in payload["policies"]:
        cash = "n/a" if row["cash_gap_rupees"] is None else f"{row['cash_gap_rupees']:,.0f}"
        lines.append(
            f"{row['policy']:<16}{row['breaks_detected']:>7}{row['precision']:>7.2f}"
            f"{row['recall']:>7.2f}{row['position_gap_shares']:>9}{row['position_gap_rupees']:>12,.0f}{cash:>11}"
        )
    lines.append("")
    lines.append("per class, tape_three_way")
    for row in payload["classes"]:
        lines.append(
            f"  {row['class']:<20}{row['correct']:>4}/{row['truth']:<4} "
            f"precision {row['precision']:.2f} recall {row['recall']:.2f}"
        )
    inv = payload["invariants"]
    lines.append("")
    lines.append(
        f"explained shares {inv['total_explained_shares']}, max gap {inv['max_share_gap']} "
        f"across {inv['symbols_checked']} symbols, cash gap {inv['cash_gap_paise']} paise"
    )
    lines.append(f"sign flip sensitivity: {inv['max_share_gap_with_flipped_sign']} shares")
    tri = payload["triage"]
    lines.append("")
    lines.append(
        f"triage {tri['breaks']} breaks, budget {tri['budget']}: "
        f"impact order {tri['coverage_by_impact']:.0%}, arrival {tri['coverage_by_arrival']:.0%}, "
        f"random {tri['coverage_random']:.0%}, top ten {tri['top_ten_share']:.0%}"
    )
    lines.append(f"total exposure INR {_money(tri['impact_paise'])}")
    return "\n".join(lines)
