"""Day simulation: the required opening balance, the shortfall, and the cost.

Money is integer cents throughout. Nothing here reads a clock, the network, or a
random source; the same Day and opening balance always produce the same result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from liquidity.book import Day

CARRY_BPS_PER_DAY = 2.18  # 5.5 percent a year over 252 business days
DEFAULT_FEE_CENTS = 25_000  # one failed payout batch: SLA credit plus manual handling
DEFAULT_EMERGENCY_BPS = 10.0  # intraday facility drawn to cover a gap


@dataclass(frozen=True)
class DayResult:
    opening_cents: int
    events: int
    gap_cents: int
    peak_balance_cents: int

    @property
    def shorted(self) -> bool:
        return self.events > 0


def required_opening(day: Day) -> int:
    """Smallest opening balance that funds every payout at its scheduled minute.

    Walk the events in time order. At each payout, cash on hand must cover it.
    The requirement is the worst cumulative deficit seen at a payout instant.
    """
    offset = 0
    worst = 0
    for event in day.events:
        if event.kind == "inflow":
            offset += event.cents
        else:
            offset -= event.cents
            if -offset > worst:
                worst = -offset
    return max(0, worst)


def simulate_day(day: Day, opening_cents: int) -> DayResult:
    """Release every event against the balance. A payout that cannot be met is a gap."""
    balance = opening_cents
    events = 0
    gap = 0
    peak = opening_cents
    for event in day.events:
        if event.kind == "inflow":
            balance += event.cents
        elif balance >= event.cents:
            balance -= event.cents
        else:
            gap += event.cents - balance
            events += 1
            balance = 0  # the facility covers it, late, so the batch leaves short
        if balance > peak:
            peak = balance
    return DayResult(opening_cents=opening_cents, events=events, gap_cents=gap, peak_balance_cents=peak)


def day_cost_cents(result: DayResult, fee_cents: int, emergency_bps: float) -> int:
    """Fees per failed batch plus the facility charge on the uncovered amount."""
    emergency = int(round(result.gap_cents * emergency_bps / 10_000.0))
    return result.events * fee_cents + emergency


def carry_cost_cents(opening_cents: int, carry_bps: float = CARRY_BPS_PER_DAY) -> int:
    return int(round(opening_cents * carry_bps / 10_000.0))


def run(
    days: Sequence[Day],
    sizes: Sequence[int],
    fee_cents: int = DEFAULT_FEE_CENTS,
    emergency_bps: float = DEFAULT_EMERGENCY_BPS,
    carry_bps: float = CARRY_BPS_PER_DAY,
) -> list[DayResult]:
    """Simulate one already sized opening balance per day."""
    if len(days) != len(sizes):
        raise ValueError(f"{len(days)} days against {len(sizes)} sizes")
    out = []
    for day, size in zip(days, sizes):
        result = simulate_day(day, size)
        out.append(result)
    return out


def totals(
    results: Iterable[DayResult],
    fee_cents: int = DEFAULT_FEE_CENTS,
    emergency_bps: float = DEFAULT_EMERGENCY_BPS,
    carry_bps: float = CARRY_BPS_PER_DAY,
) -> dict:
    """Aggregate costs. The three components must add to the total exactly."""
    carry = 0
    fees = 0
    emergency = 0
    events = 0
    days = 0
    opened = 0
    for r in results:
        days += 1
        carry += carry_cost_cents(r.opening_cents, carry_bps)
        fees += r.events * fee_cents
        emergency += int(round(r.gap_cents * emergency_bps / 10_000.0))
        events += r.events
        opened += r.opening_cents
    total = carry + fees + emergency
    return {
        "days": days,
        "carry_cents": carry,
        "fee_cents": fees,
        "emergency_cents": emergency,
        "total_cents": total,
        "events": events,
        "days_shorted": sum(1 for r in results if r.shorted),  # type: ignore[union-attr]
        "mean_opening_cents": opened // days if days else 0,
    }
