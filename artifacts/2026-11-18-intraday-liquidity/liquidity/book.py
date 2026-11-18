"""Synthetic float book: card volume, acquirer settlement, merchant payouts.

Synthetic data, labeled as such. No real account, merchant, or acquirer appears
here. Every number is generated from a seed by the functions in this module.

The shape of the day is the whole point:

    09:00   acquirer settles the early slice of yesterday's card sales
    11:00   merchant payout batch one leaves
    15:00   merchant payout batch two leaves
    16:30   acquirer settles the late slice of yesterday's card sales

So the money that funds today's payouts mostly lands 90 minutes after the last
payout cutoff. That is the standard processor float, and it is why a daily net
position tells you almost nothing about whether the account can pay at 11:00.

Business days only, indexed 0..days-1, with weekday = index % 5 (0 is Monday).
No wall clock is read anywhere in this package.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

EARLY_SETTLEMENT_MINUTE = 9 * 60
PAYOUT_ONE_MINUTE = 11 * 60
PAYOUT_TWO_MINUTE = 15 * 60
LATE_SETTLEMENT_MINUTE = 16 * 60 + 30

DOW_FACTOR = (1.18, 1.02, 1.00, 1.00, 0.95)


@dataclass(frozen=True)
class Event:
    """One cash movement. `cents` is a positive magnitude; `kind` gives the sign."""

    minute: int
    kind: str
    cents: int


@dataclass(frozen=True)
class Day:
    index: int
    card_cents: int
    inflow_cents: int
    payout_cents: int
    first_batch_cents: int
    second_batch_cents: int
    early_inflow_cents: int
    late_inflow_cents: int
    slipped_in_cents: int
    events: tuple[Event, ...]

    @property
    def net_cents(self) -> int:
        """Daily net flow. Positive means the day funds itself on a daily basis."""
        return self.inflow_cents - self.payout_cents


@dataclass(frozen=True)
class BookParams:
    """Generator knobs. Stress runs change one or two of these, never the seed."""

    days: int = 720
    base_card_cents: int = 180_000_000
    card_sigma: float = 0.16
    payout_sigma: float = 0.05
    payout_t1_weight: float = 0.60
    settlement_ratio: float = 0.998
    payout_ratio: float = 0.975
    early_share_mean: float = 0.30
    early_share_sigma: float = 0.04
    first_batch_share_mean: float = 0.45
    first_batch_share_sigma: float = 0.05
    slip_rate: float = 0.04
    late_share: float = 0.70
    spike_rate: float = 0.03
    spike_mult: float = 1.70
    all_in_at_open: bool = False
    jump_at: int = 0
    jump_mult: float = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def card_volumes(seed: int, params: BookParams) -> list[int]:
    """Acquirer volume per business day, in cents."""
    rng = Random(seed)
    out = []
    for i in range(params.days):
        level = params.base_card_cents * DOW_FACTOR[i % 5]
        value = level * math.exp(rng.gauss(0.0, params.card_sigma))
        if rng.random() < params.spike_rate:
            value *= params.spike_mult
        if params.jump_at and i >= params.jump_at:
            value *= params.jump_mult
        out.append(int(value))
    return out


def build_book(seed: int, params: BookParams | None = None) -> list[Day]:
    """Build the float book. Pure function of (seed, params)."""
    p = BookParams() if params is None else params
    rng = Random(seed)
    card = card_volumes(seed, p)

    days: list[Day] = []
    carry_in_cents = 0  # late settlement that slipped from the previous day
    for i in range(p.days):
        today_card = card[i]
        settled_base = card[i - 1] if i > 0 else card[0]

        settlement = int(settled_base * p.settlement_ratio)
        early_share = _clamp(rng.gauss(p.early_share_mean, p.early_share_sigma), 0.15, 0.45)
        early = int(settlement * early_share)
        late = settlement - early

        slipped_in = carry_in_cents
        carry_in_cents = 0
        slipped_out = 0
        slips_today = rng.random() < p.slip_rate
        if p.all_in_at_open:
            # The schedule experiment. Everything settles before any payout, and
            # the random draws stay in the same order so the book is comparable.
            early = settlement
            late = 0
        elif slips_today:
            slipped_out = int(late * p.late_share)
            late -= slipped_out
            carry_in_cents = slipped_out

        # Merchants are paid on a T+1 / T+2 mix, so the payout run is not the
        # same money that settles today. That mismatch is real variance.
        prior = card[i - 1] if i > 0 else card[0]
        prior2 = card[i - 2] if i > 1 else prior
        blended = p.payout_t1_weight * prior + (1.0 - p.payout_t1_weight) * prior2
        payout = p.payout_ratio * blended * math.exp(rng.gauss(0.0, p.payout_sigma))
        if rng.random() < p.spike_rate:
            payout *= p.spike_mult
        payout = int(payout)

        share = _clamp(
            rng.gauss(p.first_batch_share_mean, p.first_batch_share_sigma), 0.25, 0.70
        )
        first = int(payout * share)
        second = payout - first

        early_available = early + slipped_in
        events = [
            Event(EARLY_SETTLEMENT_MINUTE, "inflow", early_available),
            Event(PAYOUT_ONE_MINUTE, "payout", first),
            Event(PAYOUT_TWO_MINUTE, "payout", second),
            Event(LATE_SETTLEMENT_MINUTE, "inflow", late),
        ]
        events.sort(key=lambda e: e.minute)

        days.append(
            Day(
                index=i,
                card_cents=today_card,
                inflow_cents=early_available + late,
                payout_cents=payout,
                first_batch_cents=first,
                second_batch_cents=second,
                early_inflow_cents=early_available,
                late_inflow_cents=late,
                slipped_in_cents=slipped_in,
                events=tuple(events),
            )
        )
        assert slipped_out >= 0
    return days


def book_totals(days: list[Day]) -> dict:
    """Plausibility check on the book before any prose is written about it."""
    inflow = sum(d.inflow_cents for d in days)
    payout = sum(d.payout_cents for d in days)
    return {
        "days": len(days),
        "inflow_cents": inflow,
        "payout_cents": payout,
        "net_cents": inflow - payout,
        "mean_payout_cents": payout // max(1, len(days)),
        "max_payout_cents": max(d.payout_cents for d in days),
        "mean_card_cents": sum(d.card_cents for d in days) // max(1, len(days)),
        "net_positive_days": sum(1 for d in days if d.net_cents > 0),
        "slipped_days": sum(1 for d in days if d.slipped_in_cents > 0),
    }
