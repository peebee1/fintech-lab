"""The synthetic payment book.

Every figure in the README comes from this generator plus the simulator. Amounts are
drawn log normal with a median near a real ecommerce ticket, with 1 percent of payments
inflated 25x so the book carries the two ends of the problem: a $20 coffee and a $90,000
supplier invoice, on the same rails.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

from .chain import CHAINS

MEDIAN_TICKET_USD = 140.0
SIGMA = 1.3
WHALE_SHARE = 0.01
WHALE_MULTIPLE = 25.0
MAX_TICKET_USD = 250_000.0

MIX: dict[str, int] = {"base": 1800, "polygon": 1400, "ethereum": 800}


@dataclass(frozen=True)
class Payment:
    pid: str
    chain: str
    amount_cents: int
    arrival_s: int
    inclusion_height: int
    drop_draw: float

    @property
    def amount_usd(self) -> float:
        return self.amount_cents / 100.0


def draw_amount(rng: Random) -> int:
    value = MEDIAN_TICKET_USD * math.exp(SIGMA * rng.gauss(0.0, 1.0))
    if rng.random() < WHALE_SHARE:
        value *= WHALE_MULTIPLE
    value = min(value, MAX_TICKET_USD)
    return max(100, int(round(value * 100)))


def build_book(seed: int = 20261116, days: int = 7) -> list[Payment]:
    """Deterministic book. Ids are assigned after a shuffle on purpose.

    A generator that fills one chain first, or whales first, hands the label to any
    id based tie break downstream. Shuffling before numbering keeps the id space
    meaningless.
    """
    rng = Random(seed)
    window_s = days * 86_400
    rows: list[tuple[str, int, int, float]] = []

    for chain_name, per_week in MIX.items():
        chain = CHAINS[chain_name]
        count = max(1, round(per_week * days / 7))
        for _ in range(count):
            amount = draw_amount(rng)
            arrival = rng.randrange(1, window_s)
            rows.append((chain_name, amount, arrival, rng.random()))

    rng.shuffle(rows)
    out: list[Payment] = []
    for index, (chain_name, amount, arrival, drop_draw) in enumerate(rows):
        chain = CHAINS[chain_name]
        inclusion = arrival // chain.block_time_s + 2
        out.append(
            Payment(
                pid=f"p{index:05d}",
                chain=chain_name,
                amount_cents=amount,
                arrival_s=arrival,
                inclusion_height=inclusion,
                drop_draw=drop_draw,
            )
        )
    return out


def book_summary(book: list[Payment]) -> dict:
    total = sum(p.amount_usd for p in book)
    amounts = sorted(p.amount_usd for p in book)
    median = amounts[len(amounts) // 2]
    return {
        "payments": len(book),
        "total_usd": round(total, 2),
        "median_usd": round(median, 2),
        "p99_usd": round(amounts[int(len(amounts) * 0.99)], 2),
        "max_usd": round(amounts[-1], 2),
        "per_chain": {
            name: sum(1 for p in book if p.chain == name) for name in CHAINS
        },
    }
