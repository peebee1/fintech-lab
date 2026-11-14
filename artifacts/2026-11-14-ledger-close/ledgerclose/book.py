"""A deterministic synthetic book. No real customer data, no network, no wall clock.

One payment processor account, six months: payments in, refunds out, one payout at each
month end that settles whatever the processor owes the merchant. Fees are 1.9 percent of
gross with 18 percent tax on the fee. Amounts are integer minor units (paise).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .entry import Line

FEE_RATE = 19  # basis points
TAX_RATE = 18  # percent of the fee
REFUND_PROBABILITY = 0.12
ACCOUNTS = ("bank_fees", "cash", "fee_revenue", "merchant_payable", "refund_expense", "tax_payable")


@dataclass(frozen=True)
class Txn:
    txn_id: str
    business_date: date
    kind: str
    lines: tuple[Line, ...]
    gross_minor: int

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.txn_id}"


@dataclass(frozen=True)
class Book:
    txns: tuple[Txn, ...]

    @property
    def gross_minor(self) -> int:
        return sum(txn.gross_minor for txn in self.txns)

    def __iter__(self):
        return iter(self.txns)

    def __len__(self) -> int:
        return len(self.txns)

    @property
    def periods(self) -> list[str]:
        return sorted({f"{txn.business_date.year:04d}-{txn.business_date.month:02d}" for txn in self.txns})

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for txn in self.txns:
            out[txn.kind] = out.get(txn.kind, 0) + 1
        return dict(sorted(out.items()))

    @property
    def payments(self) -> int:
        return self.counts.get("payment", 0)

    def net_minor(self) -> int:
        return sum(line.amount_minor for txn in self.txns for line in txn.lines)


def _amount(rng: random.Random) -> int:
    bucket = rng.random()
    if bucket < 0.70:
        return rng.randint(300_00, 5_000_00)
    if bucket < 0.95:
        return rng.randint(5_000_00, 50_000_00)
    return rng.randint(50_000_00, 4_00_000_00)


def _days_in(month_start: date) -> int:
    following = date(month_start.year + (month_start.month == 12), month_start.month % 12 + 1, 1)
    return (following - timedelta(days=1)).day


def build(seed: int = 7, months: int = 6, per_month: int = 40, start: str = "2026-01") -> Book:
    rng = random.Random(seed)
    year, month = (int(part) for part in start.split("-"))
    txns: list[Txn] = []

    for offset in range(months):
        index = year * 12 + (month - 1) + offset
        month_start = date(index // 12, index % 12 + 1, 1)
        last_day = _days_in(month_start)
        payable = 0
        gross_total = fee_total = refund_total = 0

        for number in range(per_month):
            day = month_start.replace(day=rng.randint(1, last_day))
            gross = _amount(rng)
            fee = round(gross * FEE_RATE / 10_000)
            tax = round(fee * TAX_RATE / 100)
            revenue = fee - tax
            txn_id = f"{month_start.year}{month_start.month:02d}{number:04d}"
            txns.append(Txn(
                txn_id=txn_id,
                business_date=day,
                kind="payment",
                gross_minor=gross,
                lines=(
                    Line("cash", gross),
                    Line("merchant_payable", -(gross - fee)),
                    Line("fee_revenue", -revenue),
                    Line("tax_payable", -tax),
                ),
            ))
            gross_total += gross
            fee_total += fee
            payable -= gross - fee

            if rng.random() < REFUND_PROBABILITY:
                refunded = max(1, round(gross * rng.uniform(0.10, 0.60)))
                txns.append(Txn(
                    txn_id=f"{txn_id}-r",
                    business_date=day,
                    kind="refund",
                    gross_minor=0,
                    lines=(Line("merchant_payable", refunded), Line("cash", -refunded)),
                ))
                refund_total += refunded
                payable += refunded

        payout = -(payable)
        if payout > 0:
            txns.append(Txn(
                txn_id=f"{month_start.year}{month_start.month:02d}-payout",
                business_date=month_start.replace(day=last_day),
                kind="payout",
                gross_minor=0,
                lines=(Line("merchant_payable", payout), Line("cash", -payout)),
            ))

    txns.sort(key=lambda txn: (txn.business_date, txn.txn_id))
    return Book(txns=tuple(txns))
