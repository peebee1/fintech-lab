"""The book: supplier invoices and the correspondent chain each one travels.

The deduction on each hop is ground truth. It is drawn once, before any policy
runs, and every policy replays the same chain, so a difference between two
policies is a difference in who pays, never in what the chain takes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Corridor:
    code: str
    source: str
    target: str
    currency: str
    hops: int
    share: float


CORRIDORS = (
    Corridor("US-IN", "US", "IN", "INR", 2, 0.30),
    Corridor("EU-IN", "EU", "IN", "INR", 2, 0.18),
    Corridor("US-MX", "US", "MX", "MXN", 1, 0.20),
    Corridor("UK-NG", "UK", "NG", "NGN", 3, 0.12),
    Corridor("US-PH", "US", "PH", "PHP", 1, 0.20),
)

# Per hop: the chance it takes a lift at all, the bps it quotes, and its floor
# and cap. Hop 3 is the cheapest and least likely to charge, which is what a
# long chain actually looks like: the last correspondent is usually reciprocal.
HOP_DEDUCT_P = (0.62, 0.48, 0.35)
HOP_BPS = (5, 11)
HOP_MIN_CENTS = (1_200, 2_500, 4_000)
HOP_MAX_CENTS = (6_000, 12_000, 20_000)
RECEIVER_P = 0.40
RECEIVER_RANGE = (1_000, 2_800)

MEDIAN_CENTS = 420_000
SIGMA = 0.85
AMOUNT_FLOOR = 35_000
AMOUNT_CEILING = 40_000_000


@dataclass(frozen=True)
class Hop:
    index: int
    bank: str
    fee_cents: int


@dataclass(frozen=True)
class Invoice:
    id: str
    day: int
    corridor: str
    hops_count: int
    currency: str
    amount_cents: int
    hops: tuple[Hop, ...]
    receiver_fee_cents: int

    @property
    def deductions_cents(self) -> int:
        """What the chain takes before the beneficiary is credited."""
        return sum(hop.fee_cents for hop in self.hops) + self.receiver_fee_cents

    @property
    def deduction_bps(self) -> float:
        return 0.0 if self.amount_cents == 0 else round(
            self.deductions_cents * 10_000 / self.amount_cents, 3
        )


@dataclass(frozen=True)
class Book:
    seed: int
    days: int
    invoices: tuple[Invoice, ...]
    corridors: tuple[Corridor, ...]

    def total_cents(self) -> int:
        return sum(inv.amount_cents for inv in self.invoices)

    def deductions_cents(self) -> int:
        return sum(inv.deductions_cents for inv in self.invoices)

    def with_corridor(self, code: str) -> list[Invoice]:
        return [inv for inv in self.invoices if inv.corridor == code]


def _pick(rng: random.Random, corridors: tuple[Corridor, ...]) -> Corridor:
    draw = rng.random()
    edge = 0.0
    for corridor in corridors:
        edge += corridor.share
        if draw < edge:
            return corridor
    return corridors[-1]


def _amount(rng: random.Random) -> int:
    dollars = rng.lognormvariate(math.log(MEDIAN_CENTS / 100), SIGMA)
    cents = int(round(dollars)) * 100
    return max(AMOUNT_FLOOR, min(AMOUNT_CEILING, cents))


def _hop(rng: random.Random, index: int, amount_cents: int) -> Hop:
    bps = round(rng.uniform(*HOP_BPS))
    takes = rng.random() < HOP_DEDUCT_P[index]
    if not takes:
        return Hop(index=index + 1, bank=f"hop-{index + 1}", fee_cents=0)
    raw = -(-amount_cents * bps // 10_000)
    fee = max(HOP_MIN_CENTS[index], min(HOP_MAX_CENTS[index], raw))
    return Hop(index=index + 1, bank=f"hop-{index + 1}", fee_cents=fee)


def generate(seed: int = 20261126, invoices: int = 2_000, days: int = 90) -> Book:
    rng = random.Random(seed)
    rows: list[Invoice] = []
    for n in range(invoices):
        corridor = _pick(rng, CORRIDORS)
        amount = _amount(rng)
        hops = tuple(_hop(rng, index, amount) for index in range(corridor.hops))
        receiver = (
            int(round(rng.uniform(*RECEIVER_RANGE))) if rng.random() < RECEIVER_P else 0
        )
        rows.append(
            Invoice(
                id=f"INV-{n + 1:05d}",
                day=rng.randrange(days),
                corridor=corridor.code,
                hops_count=corridor.hops,
                currency=corridor.currency,
                amount_cents=amount,
                hops=hops,
                receiver_fee_cents=receiver,
            )
        )
    return Book(seed=seed, days=days, invoices=tuple(rows), corridors=CORRIDORS)


def expected_bps(book: Book) -> dict[str, float]:
    """Mean deduction bps per corridor, the one number a routing rule can know."""
    out: dict[str, float] = {}
    for corridor in book.corridors:
        rows = book.with_corridor(corridor.code)
        value = sum(inv.amount_cents for inv in rows)
        taken = sum(inv.deductions_cents for inv in rows)
        out[corridor.code] = 0.0 if value == 0 else round(taken * 10_000 / value, 3)
    return out
