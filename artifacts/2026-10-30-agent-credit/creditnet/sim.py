"""A synthetic market of agents, three credit rules, and what a default costs.

Everything here is deterministic: one seed, no clock, no network. The flows are
synthetic and labeled as such. They are shaped, not random noise: most value moves
around short cycles, which is the pattern that netting exists to exploit. A sweep
over limit levels shows where each credit rule stops admitting payments.
"""

from __future__ import annotations

import random
from typing import Sequence

from .credit import GROSS, NET, RULES, UNLIMITED, CreditBook
from .ledger import Obligation
from .money import fmt
from .netting import bilateral_settlement_value, reduction, settlement_value

SEED = 20261030
MEMBERS = 12
SCENARIOS = 20
CYCLES = 18
TARGET_OBLIGATIONS = 150
LIMITS = (20_000, 40_000, 60_000, 90_000, 150_000)  # $200 to $1,500 of credit
REFERENCE_LIMIT = 60_000  # $600, the level the summary table reports


def member_names(count: int = MEMBERS) -> tuple[str, ...]:
    return tuple(f"agent-{index:02d}" for index in range(count))


def market(
    scenario: int,
    seed: int = SEED,
    members: Sequence[str] | None = None,
) -> tuple[Obligation, ...]:
    """One window of obligations: liquidity cycles plus one way noise flow."""
    names = list(members or member_names())
    rng = random.Random(f"{seed}:{scenario}")
    items: list[Obligation] = []
    counter = 0

    for _ in range(CYCLES):
        size = rng.choice((3, 3, 4, 5))
        ring = rng.sample(names, size)
        base = rng.randrange(4_000, 20_000, 100)
        for index in range(size):
            items.append(
                Obligation(
                    id=counter,
                    payer=ring[index],
                    payee=ring[(index + 1) % size],
                    amount=base + rng.randrange(0, 500),
                    ts=counter,
                )
            )
            counter += 1

    while len(items) < TARGET_OBLIGATIONS:
        payer, payee = rng.sample(names, 2)
        items.append(
            Obligation(
                id=counter,
                payer=payer,
                payee=payee,
                amount=rng.randrange(500, 6_000, 50),
                ts=counter,
            )
        )
        counter += 1

    return tuple(items)


def limits_for(members: Sequence[str], limit: int) -> dict[str, int]:
    return {member: limit for member in members}


def run(offered: Sequence[Obligation], limits: dict[str, int], rule: str) -> CreditBook:
    book = CreditBook(limits, rule)
    for obligation in offered:
        book.admit(obligation)
    return book


def worst_debtor(book: CreditBook) -> str:
    positions = book.ledger.net_positions()
    if not positions:
        return ""
    return min(positions, key=lambda member: (positions[member], member))


def window(scenario: int, limit: int, seed: int = SEED) -> dict:
    """One settlement window under every rule, at one limit level."""
    names = member_names()
    offered = market(scenario, seed=seed, members=names)
    limits = limits_for(names, limit)
    books = {rule: run(offered, limits, rule) for rule in RULES}

    base = books[UNLIMITED]
    victim = worst_debtor(base)
    positions = base.ledger.net_positions()

    policies = {}
    for rule in RULES:
        book = books[rule]
        final = book.ledger.net_positions()
        policies[rule] = {
            "admitted": len(book.ledger),
            "admitted_value": book.admitted_value(),
            "rejected": len(book.rejected),
            "rejected_value": book.rejected_value(),
            "max_net_debit": book.max_net_debit(),
            "members_over_limit": sum(1 for value in final.values() if -value > limit),
            "default_loss": max(0, -book.position(victim)),
            "settled_value": settlement_value(book.ledger),
            "balanced": book.ledger.imbalance() == 0,
        }

    return {
        "scenario": scenario,
        "limit": limit,
        "offered": len(offered),
        "offered_value": base.ledger.gross_value(),
        "bilateral_value": bilateral_settlement_value(base.ledger),
        "multilateral_value": settlement_value(base.ledger),
        "netting_reduction_pct": round(100 * reduction(base.ledger), 2),
        "imbalance": base.ledger.imbalance(),
        "victim": victim,
        "victim_net_debit": max(0, -positions.get(victim, 0)),
        "victim_gross_outflow": base.ledger.outflow(victim),
        "policies": policies,
    }


def _aggregate(windows: list[dict], limit: int) -> dict[str, dict]:
    rules = {}
    for rule in RULES:
        offered_value = sum(row["offered_value"] for row in windows)
        admitted_value = sum(row["policies"][rule]["admitted_value"] for row in windows)
        rules[rule] = {
            "admitted_obligations": sum(row["policies"][rule]["admitted"] for row in windows),
            "admitted_value": admitted_value,
            "rejected_obligations": sum(row["policies"][rule]["rejected"] for row in windows),
            "rejected_value": sum(row["policies"][rule]["rejected_value"] for row in windows),
            "admitted_share_pct": round(100 * admitted_value / offered_value, 2),
            "settled_value": sum(row["policies"][rule]["settled_value"] for row in windows),
            "worst_net_debit": max(row["policies"][rule]["max_net_debit"] for row in windows),
            "windows_over_limit": sum(
                1 for row in windows if row["policies"][rule]["max_net_debit"] > limit
            ),
            "total_default_loss": sum(row["policies"][rule]["default_loss"] for row in windows),
            "worst_default_loss": max(row["policies"][rule]["default_loss"] for row in windows),
        }
    return rules


def experiments(seed: int = SEED, scenarios: int = SCENARIOS) -> dict:
    windows = [window(index, REFERENCE_LIMIT, seed=seed) for index in range(scenarios)]
    sweep = []
    for limit in LIMITS:
        rows = windows if limit == REFERENCE_LIMIT else [
            window(index, limit, seed=seed) for index in range(scenarios)
        ]
        sweep.append({
            "limit": limit,
            "limit_display": fmt(limit),
            "rules": _aggregate(rows, limit),
        })

    total_gross = sum(row["offered_value"] for row in windows)
    total_multi = sum(row["multilateral_value"] for row in windows)
    total_bilateral = sum(row["bilateral_value"] for row in windows)
    victim_net = [row["victim_net_debit"] for row in windows]
    victim_gross = [row["victim_gross_outflow"] for row in windows]
    reference = next(entry for entry in sweep if entry["limit"] == REFERENCE_LIMIT)

    return {
        "meta": {
            "seed": seed,
            "scenarios": scenarios,
            "members": MEMBERS,
            "reference_limit": REFERENCE_LIMIT,
            "reference_limit_display": fmt(REFERENCE_LIMIT),
            "limits": list(LIMITS),
            "synthetic": True,
            "note": "Synthetic agent flows. No real counterparties, no real credit data.",
        },
        "netting": {
            "gross_value": total_gross,
            "bilateral_value": total_bilateral,
            "multilateral_value": total_multi,
            "multilateral_reduction_pct": round(100 * (1 - total_multi / total_gross), 2),
            "bilateral_reduction_pct": round(100 * (1 - total_bilateral / total_gross), 2),
            "all_windows_balanced": all(row["imbalance"] == 0 for row in windows),
            "mean_reduction_pct": round(
                sum(row["netting_reduction_pct"] for row in windows) / len(windows), 2
            ),
        },
        "reference": reference,
        "sweep": sweep,
        "default": {
            "victim_is_largest_net_debtor": True,
            "mean_victim_net_debit": round(sum(victim_net) / len(victim_net)),
            "mean_victim_gross_outflow": round(sum(victim_gross) / len(victim_gross)),
            "mean_close_out_ratio": round(
                sum(g / max(1, n) for g, n in zip(victim_gross, victim_net)) / len(windows), 2
            ),
            "reference_fund_needed": reference["rules"][NET]["worst_net_debit"],
            "unlimited_fund_needed": reference["rules"][UNLIMITED]["worst_net_debit"],
            "limit_covers_worst_loss": reference["rules"][NET]["worst_default_loss"]
            <= REFERENCE_LIMIT,
        },
        "windows": [
            {
                "scenario": row["scenario"],
                "offered": row["offered"],
                "gross_value": row["offered_value"],
                "bilateral_value": row["bilateral_value"],
                "multilateral_value": row["multilateral_value"],
                "reduction_pct": row["netting_reduction_pct"],
                "imbalance": row["imbalance"],
            }
            for row in windows
        ],
    }


def summary_text(payload: dict) -> str:
    net = payload["netting"]
    ref = payload["reference"]["rules"]
    dep = payload["default"]
    limit = payload["meta"]["reference_limit_display"]
    lines = [
        f"synthetic market: {payload['meta']['members']} agents, "
        f"{payload['meta']['scenarios']} windows, limit {limit} per member per window",
        "",
        f"gross flow            {fmt(net['gross_value'])}",
        f"bilateral netting     {fmt(net['bilateral_value'])}  "
        f"(-{net['bilateral_reduction_pct']:.2f}%)",
        f"multilateral netting  {fmt(net['multilateral_value'])}  "
        f"(-{net['multilateral_reduction_pct']:.2f}%)",
        f"every window balances {net['all_windows_balanced']}",
        "",
        f"{'rule':<12}{'admitted':>10}{'value':>14}{'share':>8}{'worst debit':>13}{'worst loss':>13}",
    ]
    for rule in RULES:
        entry = ref[rule]
        lines.append(
            f"{rule:<12}{entry['admitted_obligations']:>10}"
            f"{fmt(entry['admitted_value']):>14}"
            f"{entry['admitted_share_pct']:>7.1f}%"
            f"{fmt(entry['worst_net_debit']):>13}"
            f"{fmt(entry['worst_default_loss']):>13}"
        )
    lines += [
        "",
        f"largest debtor pays {fmt(dep['mean_victim_net_debit'])} net, "
        f"after sending {fmt(dep['mean_victim_gross_outflow'])} gross "
        f"({dep['mean_close_out_ratio']:.1f}x)",
        f"fund to cover the worst window: {fmt(dep['reference_fund_needed'])} net debit"
        f" (no limit rule: {fmt(dep['unlimited_fund_needed'])})",
        f"the {limit} limit covers the worst loss: {dep['limit_covers_worst_loss']}",
    ]
    return "\n".join(lines)
