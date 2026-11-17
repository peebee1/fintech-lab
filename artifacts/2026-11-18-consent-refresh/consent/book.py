"""The synthetic consent book.

A payer authorises a merchant to debit an account on a schedule. The authorisation
carries a rail maximum lifetime. Every re-authorisation is a prompt the customer can
walk away from, and the walk away rate depends on when the prompt lands.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

HORIZON_DAYS = 360
MONTH_DAYS = 30
PAY_HOUR = 10
PROMPT_HOUR = 18

# Rail maximum consent lifetime in this model. Modelled on the 90 day
# re-authentication rule that open banking regimes apply to long lived consents.
LIFETIME_DAYS = 90

# A prompt sent this close to a scheduled debit is treated as contextual: it arrives
# while the customer is already dealing with that payment.
CONTEXT_DAYS = 3

MERCHANTS = (
    "amber-energy",
    "bright-broadband",
    "cobalt-cloud",
    "delta-gym",
    "ember-insurance",
    "fable-mobile",
    "granite-storage",
    "harbor-news",
    "ivory-streaming",
    "juniper-pharmacy",
    "kestrel-transit",
    "lantern-learning",
)


@dataclass(frozen=True)
class Payer:
    pid: str
    merchant: str
    bill_cents: int
    due_day: int
    consent_start: int
    latency_median_h: float
    abandon_prob: float
    churn_hazard: float

    @property
    def due_days(self) -> tuple[int, ...]:
        """Every scheduled debit in the year, monthly on a fixed day."""
        out = []
        for month in range(HORIZON_DAYS // MONTH_DAYS):
            day = month * MONTH_DAYS + self.due_day
            if self.consent_start <= day < HORIZON_DAYS:
                out.append(day)
        return tuple(out)


def build_book(seed: int = 20261118, size: int = 1200) -> list[Payer]:
    """Build the payer book. Deterministic for a given seed and size."""
    rng = random.Random(seed)
    payers: list[Payer] = []
    for index in range(size):
        bill = int(round(rng.lognormvariate(math.log(3200), 0.55)))
        payers.append(
            Payer(
                pid=f"C{index:04d}",
                merchant=MERCHANTS[index % len(MERCHANTS)],
                bill_cents=max(500, min(40_000, bill)),
                due_day=rng.randint(1, 28),
                consent_start=rng.randint(0, 29),
                latency_median_h=round(rng.lognormvariate(math.log(20.0), 0.9), 2),
                abandon_prob=round(rng.uniform(0.03, 0.20), 4),
                churn_hazard=round(rng.uniform(0.004, 0.030), 4),
            )
        )
    return payers


def annual_value_cents(payers: list[Payer]) -> int:
    """Value of every scheduled debit if no consent ever expired and nobody churned."""
    return sum(p.bill_cents * len(p.due_days) for p in payers)
