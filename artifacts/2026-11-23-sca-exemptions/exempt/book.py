"""A synthetic book of remote card payments.

Deterministic for a seed. Amounts are integer cents, the risk score is drawn
conditional on the latent fraud label so the score carries real information,
and the outcome draws are columns on the transaction so every policy replays
the same draws in the same order.
"""

from __future__ import annotations

import bisect
import math
import random
from dataclasses import dataclass

CHANNELS = (("app", 0.55), ("web", 0.45))

# name, share, fraud multiplier
MCC = (
    ("groceries", 0.24, 0.45),
    ("fashion", 0.20, 1.20),
    ("digital", 0.20, 2.10),
    ("electronics", 0.15, 1.70),
    ("home", 0.12, 0.90),
    ("travel", 0.09, 1.50),
)

FRAUD_BASE = 0.0007
MEDIAN_CENTS = 3800
SIGMA = 0.95
MIN_CENTS = 200
MAX_CENTS = 150_000
SHOPPERS = 5200
SECOND_CARD_SHARE = 0.22


@dataclass(frozen=True)
class Txn:
    id: int
    day: int
    amount_cents: int
    channel: str
    mcc: str
    card: str
    risk: float
    is_fraud: bool
    abandon_draw: float
    stop_draw: float


@dataclass(frozen=True)
class Book:
    txns: tuple[Txn, ...]
    days: int

    def __len__(self) -> int:
        return len(self.txns)

    def value_cents(self) -> int:
        return sum(t.amount_cents for t in self.txns)

    def latent_fraud_cents(self) -> int:
        return sum(t.amount_cents for t in self.txns if t.is_fraud)

    def latent_fraud_bps(self) -> float:
        value = self.value_cents()
        return 0.0 if value == 0 else self.latent_fraud_cents() * 10000.0 / value

    def mean_ticket_cents(self) -> int:
        return self.value_cents() // len(self.txns)


def _pick(rng: random.Random, weights: tuple[tuple[str, float, float], ...]) -> tuple[str, float]:
    roll = rng.random()
    running = 0.0
    for name, share, mult in weights:
        running += share
        if roll <= running:
            return name, mult
    name, _, mult = weights[-1]
    return name, mult


def _shopper_picker(rng: random.Random) -> list[float]:
    weights = [1.0 / ((i + 1) ** 0.85) for i in range(SHOPPERS)]
    total = 0.0
    cumulative = []
    for weight in weights:
        total += weight
        cumulative.append(total)
    return [value / total for value in cumulative]


def generate(seed: int = 20261123, days: int = 60, per_day: int = 800) -> Book:
    """Build the book. Ids are chronological and no decision reads them."""
    rng = random.Random(seed)
    picker = _shopper_picker(rng)
    mu = math.log(MEDIAN_CENTS)
    txns: list[Txn] = []
    for day in range(days):
        count = per_day + rng.randint(-45, 45)
        if day % 7 in (5, 6):
            count = int(count * 1.15)
        for _ in range(count):
            mcc, mcc_mult = _pick(rng, MCC)
            channel = "app" if rng.random() < CHANNELS[0][1] else "web"
            cents = int(round(math.exp(mu + SIGMA * rng.gauss(0.0, 1.0))))
            cents = max(MIN_CENTS, min(MAX_CENTS, cents))
            amount_factor = min(2.5, max(0.4, cents / 4200.0))
            p_fraud = FRAUD_BASE * mcc_mult * amount_factor
            is_fraud = rng.random() < p_fraud
            risk = rng.betavariate(2.4, 2.2) if is_fraud else rng.betavariate(2.0, 10.0)
            shopper = bisect.bisect_left(picker, rng.random())
            card = f"{shopper}" if rng.random() >= SECOND_CARD_SHARE else f"{shopper}-1"
            txns.append(
                Txn(
                    id=len(txns),
                    day=day,
                    amount_cents=cents,
                    channel=channel,
                    mcc=mcc,
                    card=card,
                    risk=risk,
                    is_fraud=is_fraud,
                    abandon_draw=rng.random(),
                    stop_draw=rng.random(),
                )
            )
    return Book(txns=tuple(txns), days=days)
