"""Replay every policy over the same book and price the outcome.

Money is integer cents. The outcome draws live on the transaction, so changing a
policy changes only the decision, never the underlying randomness, which keeps the
policies comparable transaction by transaction.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from .book import Book, Txn, generate
from .policies import (
    CHALLENGE,
    LOW_VALUE,
    TRA,
    Decision,
    Policy,
    State,
    all_policies,
)
from .rules import bps, reference_bps

RESULTS = Path(__file__).resolve().parents[1] / "results"


@dataclass(frozen=True)
class Config:
    stop_rate: float = 0.88
    chargeback_fee_cents: int = 1200
    margin_pct: int = 22
    lag_days: int = 2
    window_days: int = 7


CONFIG = Config()


def abandon_probability(txn: Txn) -> float:
    base = 0.038 if txn.channel == "app" else 0.072
    return min(0.5, base * (1.0 + 0.35 * math.exp(-txn.amount_cents / 3000.0)))


@dataclass
class Result:
    policy: str
    transactions: int
    processed_cents: int
    exempt_txn: int
    exempt_cents: int
    low_value_txn: int
    tra_txn: int
    challenges: int
    abandoned: int
    abandoned_cents: int
    lost_margin_cents: int
    fraud_cases: int
    fraud_loss_cents: int
    chargeback_fees_cents: int
    total_cost_cents: int
    realized_fraud_bps: float
    breach_days: int
    max_overshoot_bps: float
    etv_days: dict[str, int]
    counter_refusals: int
    low_value_exemptions: int

    def as_dict(self) -> dict:
        return asdict(self)


def estimate_bps(
    fraud_cents: list[int], value_cents: list[int], day: int, cfg: Config
) -> float | None:
    hi = day - cfg.lag_days
    lo = hi - cfg.window_days + 1
    if lo < 0:
        return None
    window_fraud = sum(fraud_cents[lo : hi + 1])
    window_value = sum(value_cents[lo : hi + 1])
    if window_value == 0:
        return None
    return bps(window_fraud, window_value)


def replay(book: Book, policy: Policy, cfg: Config = CONFIG) -> Result:
    state = State()
    fraud_cents = [0] * book.days
    value_cents = [0] * book.days
    etvs: list[int] = []

    exempt_txn = low_value_txn = tra_txn = 0
    exempt_cents = challenges = 0
    abandoned = abandoned_cents = lost_margin = 0
    fraud_cases = fraud_loss = fees = 0

    day = 0
    etv = policy.etv_for(estimate_bps(fraud_cents, value_cents, 0, cfg))
    etvs.append(etv)

    for txn in book.txns:
        while txn.day > day:
            day += 1
            etv = policy.etv_for(estimate_bps(fraud_cents, value_cents, day, cfg))
            etvs.append(etv)

        decision: Decision = policy.decide(txn, etv, state)
        value_cents[txn.day] += txn.amount_cents

        if decision.exempt:
            exempt_txn += 1
            exempt_cents += txn.amount_cents
            if decision.basis == LOW_VALUE:
                low_value_txn += 1
            elif decision.basis == TRA:
                tra_txn += 1
        else:
            challenges += 1

        if decision.exempt and txn.is_fraud:
            fraud_cases += 1
            fraud_loss += txn.amount_cents
            fees += cfg.chargeback_fee_cents
            fraud_cents[txn.day] += txn.amount_cents
        elif not decision.exempt and txn.is_fraud and txn.stop_draw >= cfg.stop_rate:
            fraud_cases += 1
            fraud_loss += txn.amount_cents
            fees += cfg.chargeback_fee_cents
            fraud_cents[txn.day] += txn.amount_cents
        elif not decision.exempt and not txn.is_fraud and txn.abandon_draw < abandon_probability(txn):
            abandoned += 1
            abandoned_cents += txn.amount_cents
            lost_margin += txn.amount_cents * cfg.margin_pct // 100

    breach_days = 0
    overshoot = 0.0
    for index, day_etv in enumerate(etvs):
        ref = reference_bps(day_etv)
        if ref is None:
            continue
        lo = max(0, index - cfg.window_days + 1)
        rate = bps(sum(fraud_cents[lo : index + 1]), sum(value_cents[lo : index + 1]))
        if rate > ref:
            breach_days += 1
            overshoot = max(overshoot, rate - ref)

    processed = sum(value_cents)
    etv_days: dict[str, int] = {}
    for day_etv in etvs:
        key = f"{day_etv / 100:.0f}" if day_etv else "none"
        etv_days[key] = etv_days.get(key, 0) + 1

    return Result(
        policy=policy.name,
        transactions=len(book.txns),
        processed_cents=processed,
        exempt_txn=exempt_txn,
        exempt_cents=exempt_cents,
        low_value_txn=low_value_txn,
        tra_txn=tra_txn,
        challenges=challenges,
        abandoned=abandoned,
        abandoned_cents=abandoned_cents,
        lost_margin_cents=lost_margin,
        fraud_cases=fraud_cases,
        fraud_loss_cents=fraud_loss,
        chargeback_fees_cents=fees,
        total_cost_cents=fraud_loss + fees + lost_margin,
        realized_fraud_bps=bps(fraud_loss, processed),
        breach_days=breach_days,
        max_overshoot_bps=round(overshoot, 2),
        etv_days=etv_days,
        counter_refusals=state.counter_refusals,
        low_value_exemptions=state.low_value_exemptions,
    )


def run(seed: int = 20261123, days: int = 60, per_day: int = 800, cfg: Config = CONFIG) -> dict:
    book = generate(seed, days=days, per_day=per_day)
    results = [replay(book, policy, cfg) for policy in all_policies()]
    by_name = {result.policy: result for result in results}
    compliant = [r for r in results if r.breach_days == 0]
    best_compliant = min(compliant, key=lambda r: r.total_cost_cents) if compliant else None
    floor = min(results, key=lambda r: r.total_cost_cents)
    baseline = by_name["challenge_all"]
    return {
        "seed": seed,
        "days": book.days,
        "transactions": len(book),
        "processed_cents": book.value_cents(),
        "mean_ticket_cents": book.mean_ticket_cents(),
        "latent_fraud_bps": round(book.latent_fraud_bps(), 2),
        "config": asdict(cfg),
        "policies": [r.as_dict() for r in results],
        "headline": {
            "challenge_all_cost_cents": baseline.total_cost_cents,
            "challenge_all_abandoned": baseline.abandoned,
            "floor_policy": floor.policy,
            "floor_cost_cents": floor.total_cost_cents,
            "best_compliant_policy": best_compliant.policy if best_compliant else None,
            "best_compliant_cost_cents": best_compliant.total_cost_cents if best_compliant else None,
            "compliant_saving_pct_vs_challenge_all": round(
                100.0 * (baseline.total_cost_cents - best_compliant.total_cost_cents)
                / baseline.total_cost_cents,
                1,
            )
            if best_compliant
            else None,
            "compliance_premium_cents": (
                best_compliant.total_cost_cents - floor.total_cost_cents
            )
            if best_compliant
            else None,
        },
    }


def render_markdown(summary: dict) -> str:
    lines = [
        "# Replay",
        "",
        f"Seed {summary['seed']}, {summary['days']} days, "
        f"{summary['transactions']:,} transactions, "
        f"EUR {summary['processed_cents'] / 100:,.2f} processed, "
        f"latent fraud {summary['latent_fraud_bps']:.2f} bps of value.",
        "",
        "| policy | exempt % txn | exempt % value | challenges | abandoned | fraud loss | friction | total | breach days |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["policies"]:
        lines.append(
            "| {policy} | {exempt:,.0f} | {value:.1f}% | {ch:,.0f} | {ab:,.0f} | "
            "{fraud:,.0f} | {fric:,.0f} | {total:,.0f} | {breach} |".format(
                policy=row["policy"],
                exempt=100.0 * row["exempt_txn"] / row["transactions"],
                value=100.0 * row["exempt_cents"] / row["processed_cents"],
                ch=row["challenges"],
                ab=row["abandoned"],
                fraud=(row["fraud_loss_cents"] + row["chargeback_fees_cents"]) / 100,
                fric=row["lost_margin_cents"] / 100,
                total=row["total_cost_cents"] / 100,
                breach=row["breach_days"],
            )
        )
    lines.append("")
    lines.append("Costs in EUR. Friction is lost contribution margin on abandoned checkouts.")
    return "\n".join(lines) + "\n"


def write_results(
    directory: Path | None = None, seed: int = 20261123, days: int = 60, per_day: int = 800
) -> Path:
    target = RESULTS if directory is None else Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    summary = run(seed, days=days, per_day=per_day)
    (target / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (target / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    return target


def summarise(summary: dict) -> list[str]:
    head = summary["headline"]
    return [
        f"book: {summary['transactions']:,} transactions, "
        f"EUR {summary['processed_cents'] / 100:,.2f}, "
        f"latent fraud {summary['latent_fraud_bps']:.2f} bps",
        f"challenge all: EUR {head['challenge_all_cost_cents'] / 100:,.2f}, "
        f"{head['challenge_all_abandoned']:,} abandoned",
        f"floor ({head['floor_policy']}): EUR {head['floor_cost_cents'] / 100:,.2f}",
        f"best compliant ({head['best_compliant_policy']}): "
        f"EUR {head['best_compliant_cost_cents'] / 100:,.2f}"
        if head["best_compliant_policy"]
        else "best compliant: none",
        f"saving vs challenge all: {head['compliant_saving_pct_vs_challenge_all']}%"
        if head["compliant_saving_pct_vs_challenge_all"] is not None
        else "saving: n/a",
        f"compliance premium over the floor: EUR "
        f"{head['compliance_premium_cents'] / 100:,.2f}"
        if head["compliance_premium_cents"] is not None
        else "compliance premium: n/a",
    ]
