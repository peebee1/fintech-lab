"""A synthetic ATM network and its demand.

The book is generated once, before any policy runs, so every policy replays the
same demand in the same order. Day 0 is a Monday on a demand calendar with no
calendar dates: weekday shape and a 30 day payday cycle are all the book needs,
and nothing reads the wall clock.

Money is integer paise. A note is a fixed denomination, which is a stated limit.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

NOTE_PAISE = 50_000  # one note is INR 500
NOTES_PER_CASSETTE = 2_500

# kind, sites, base withdrawals per day, mean notes per withdrawal, cassettes
KINDS = (
    ("metro", 24, 160, 7.0, 4),
    ("payday", 16, 120, 6.0, 4),
    ("resort", 12, 95, 8.0, 4),
    ("low_traffic", 8, 22, 5.0, 3),
)

# Monday to Sunday, index 0 is Monday.
WEEKDAY = {
    "metro": (1.05, 1.00, 1.00, 1.05, 1.20, 1.10, 0.70),
    "payday": (1.05, 1.00, 1.00, 1.05, 1.15, 1.05, 0.75),
    "resort": (0.75, 0.70, 0.75, 0.85, 1.20, 1.50, 1.45),
    "low_traffic": (1.00, 1.00, 1.00, 1.00, 1.05, 1.05, 0.95),
}

SURGE_DAYS = range(60, 65)  # a demand surge no trailing forecast has seen
SURGE_FACTOR = 1.55


@dataclass(frozen=True)
class Site:
    id: int
    kind: str
    base_withdrawals: int
    mean_notes: float
    cassettes: int

    @property
    def capacity(self) -> int:
        return self.cassettes * NOTES_PER_CASSETTE

    @property
    def opening(self) -> int:
        return self.capacity // 2

    @property
    def schedule_weekday(self) -> int:
        return self.id % 7

    @property
    def base_notes(self) -> float:
        return self.base_withdrawals * self.mean_notes


@dataclass(frozen=True)
class DayDemand:
    day: int
    withdrawals: int
    notes: int


@dataclass(frozen=True)
class Book:
    sites: tuple[Site, ...]
    rows: dict[int, tuple[DayDemand, ...]]
    days: int
    seed: int

    def notes_dispensed(self) -> int:
        return sum(row.notes for site in self.sites for row in self.rows[site.id])

    def withdrawals(self) -> int:
        return sum(row.withdrawals for site in self.sites for row in self.rows[site.id])

    def site_notes(self, site_id: int) -> int:
        return sum(row.notes for row in self.rows[site_id])


def _poisson(rng: random.Random, lam: float) -> int:
    """Inverse transform on the exponential, exact and cheap for lam under a few hundred."""
    if lam <= 0:
        return 0
    total = 0.0
    k = 0
    while True:
        total += -math.log(1.0 - rng.random())
        if total > lam:
            return k
        k += 1


def _month_factor(kind: str, cycle_day: int) -> float:
    if kind == "payday":
        if cycle_day in (0, 1):
            return 1.40
        if cycle_day >= 28:
            return 1.25
        return 1.0
    if kind == "metro":
        if cycle_day in (0, 1):
            return 1.12
        if cycle_day >= 28:
            return 1.10
        return 1.0
    return 1.0


def generate(seed: int = 20261125, days: int = 120) -> Book:
    """Build the network and one demand row per site per day."""
    rng = random.Random(seed)
    sites: list[Site] = []
    rows: dict[int, tuple[DayDemand, ...]] = {}
    for kind, count, base_w, mean_notes, cassettes in KINDS:
        for _ in range(count):
            site = Site(
                id=len(sites),
                kind=kind,
                base_withdrawals=base_w,
                mean_notes=mean_notes,
                cassettes=cassettes,
            )
            sites.append(site)
            series: list[DayDemand] = []
            for day in range(days):
                factor = WEEKDAY[kind][day % 7] * _month_factor(kind, day % 30)
                if day in SURGE_DAYS:
                    factor *= SURGE_FACTOR
                lam = base_w * factor
                withdrawals = _poisson(rng, lam)
                notes = 0
                for _ in range(withdrawals):
                    notes += 1 + _poisson(rng, max(0.0, mean_notes - 1.0))
                series.append(DayDemand(day=day, withdrawals=withdrawals, notes=notes))
            rows[site.id] = tuple(series)
    return Book(sites=tuple(sites), rows=rows, days=days, seed=seed)
