"""Replay one policy over the book and price what it costs.

Three cost lines, and they must sum to the total:

    cit       the trip fee plus a per note handling charge, premium on an emergency trip
    capital   closing inventory valued at the note price, held for a day at the funding rate
    lost      unserved withdrawals, priced at the interchange a served one earns

Cash conservation is asserted per site per day: opening plus delivered equals
dispensed plus closing, and closing stays inside capacity.
"""

from __future__ import annotations

from dataclasses import dataclass

from .book import NOTES_PER_CASSETTE, NOTE_PAISE, Book, Site
from .policies import Policy

RATE_BPS = 750
VISIT_PAISE = 170_000
EMERGENCY_VISIT_PAISE = 360_000
HANDLING_PAISE_PER_NOTE = 20
LOST_WITHDRAWAL_PAISE = 2_100


@dataclass(frozen=True)
class SiteResult:
    site_id: int
    kind: str
    visits: int
    emergency_visits: int
    delivered: int
    dispensed: int
    lost_notes: int
    withdrawals: int
    served: int
    stockout_days: int
    cit_paise: int
    balance_paise_days: int


@dataclass(frozen=True)
class Result:
    policy: str
    sites: tuple[SiteResult, ...]
    days: int
    violations: tuple[str, ...]

    def _sum(self, field: str) -> int:
        return sum(getattr(s, field) for s in self.sites)

    @property
    def visits(self) -> int:
        return self._sum("visits")

    @property
    def emergency_visits(self) -> int:
        return self._sum("emergency_visits")

    @property
    def delivered(self) -> int:
        return self._sum("delivered")

    @property
    def dispensed(self) -> int:
        return self._sum("dispensed")

    @property
    def lost_notes(self) -> int:
        return self._sum("lost_notes")

    @property
    def withdrawals(self) -> int:
        return self._sum("withdrawals")

    @property
    def served(self) -> int:
        return self._sum("served")

    @property
    def lost_withdrawals(self) -> int:
        return self.withdrawals - self.served

    @property
    def stockout_days(self) -> int:
        return self._sum("stockout_days")

    @property
    def cit_paise(self) -> int:
        return self._sum("cit_paise")

    @property
    def balance_paise_days(self) -> int:
        return self._sum("balance_paise_days")

    @property
    def capital_paise(self) -> int:
        return self.balance_paise_days * RATE_BPS // (10_000 * 365)

    @property
    def lost_paise(self) -> int:
        return self.lost_withdrawals * LOST_WITHDRAWAL_PAISE

    @property
    def total_paise(self) -> int:
        return self.cit_paise + self.capital_paise + self.lost_paise

    @property
    def service_level(self) -> float:
        return 0.0 if self.withdrawals == 0 else self.served / self.withdrawals

    @property
    def mean_balance_notes(self) -> float:
        site_days = len(self.sites) * self.days
        return 0.0 if site_days == 0 else self.balance_paise_days / NOTE_PAISE / site_days

    def by_kind(self) -> list[dict]:
        kinds = sorted({s.kind for s in self.sites})
        rows = []
        for kind in kinds:
            group = [s for s in self.sites if s.kind == kind]
            withdrawn = sum(s.withdrawals for s in group)
            served = sum(s.served for s in group)
            rows.append(
                {
                    "kind": kind,
                    "sites": len(group),
                    "visits": sum(s.visits for s in group),
                    "withdrawals": withdrawn,
                    "served_withdrawals": served,
                    "lost_withdrawals": withdrawn - served,
                    "service_level": 0.0 if withdrawn == 0 else round(served / withdrawn, 6),
                    "stockout_days": sum(s.stockout_days for s in group),
                    "cit_paise": sum(s.cit_paise for s in group),
                    "capital_paise": sum(s.balance_paise_days for s in group) * RATE_BPS // (10_000 * 365),
                }
            )
        return rows


def run(book: Book, policy: Policy) -> Result:
    """Replay one policy over every site, day by day, and check the invariants."""
    violations: list[str] = []
    site_results: list[SiteResult] = []
    for site in book.sites:
        capacity = site.capacity
        inventory = site.opening
        visits = emergency = delivered = dispensed = lost = served = stockout_days = 0
        cit = balance_days = 0
        for row in book.rows[site.id]:
            forecast = policy.forecast_notes(book, site, row.day)
            order, is_emergency = policy.decide(site, row.day, inventory, forecast)
            order = max(0, min(order, capacity - inventory))
            opening = inventory
            if order > 0:
                visits += 1
                delivered += order
                emergency += 1 if is_emergency else 0
                fee = EMERGENCY_VISIT_PAISE if is_emergency else VISIT_PAISE
                cit += fee + order * HANDLING_PAISE_PER_NOTE
            inventory += order

            served_notes = min(inventory, row.notes)
            day_served = row.withdrawals
            if served_notes < row.notes:
                day_served = round(row.withdrawals * served_notes / row.notes)
                lost += row.notes - served_notes
                stockout_days += 1
            served += day_served
            dispensed += served_notes
            inventory -= served_notes
            closing = inventory

            if opening + order != served_notes + closing:
                violations.append(f"site {site.id} day {row.day}: conservation")
            if not 0 <= closing <= capacity:
                violations.append(f"site {site.id} day {row.day}: closing {closing} outside capacity")
            balance_days += closing
        site_results.append(
            SiteResult(
                site_id=site.id,
                kind=site.kind,
                visits=visits,
                emergency_visits=emergency,
                delivered=delivered,
                dispensed=dispensed,
                lost_notes=lost,
                withdrawals=sum(r.withdrawals for r in book.rows[site.id]),
                served=served,
                stockout_days=stockout_days,
                cit_paise=cit,
                balance_paise_days=balance_days * NOTE_PAISE,
            )
        )
    return Result(policy=policy.name, sites=tuple(site_results), days=book.days, violations=tuple(violations))


def with_cassettes(book: Book, cassettes: int) -> Book:
    """The same demand and the same site list, every machine holding this many cassettes."""
    sites = tuple(
        Site(
            id=site.id,
            kind=site.kind,
            base_withdrawals=site.base_withdrawals,
            mean_notes=site.mean_notes,
            cassettes=cassettes,
        )
        for site in book.sites
    )
    return Book(sites=sites, rows=book.rows, days=book.days, seed=book.seed)


def sweep_capacity(book: Book, policy: Policy, cassettes: tuple[int, ...] = (2, 3, 4, 5, 6)) -> list[dict]:
    """Uniform capacity sweep. Demand is fixed before any policy runs, so only capacity moves."""
    rows = []
    for count in cassettes:
        result = run(with_cassettes(book, count), policy)
        rows.append(
            {
                "cassettes": count,
                "capacity_notes": count * NOTES_PER_CASSETTE,
                "visits": result.visits,
                "emergency_visits": result.emergency_visits,
                "service_level": round(result.service_level, 6),
                "stockout_site_days": result.stockout_days,
                "total_paise": result.total_paise,
                "cit_paise": result.cit_paise,
                "capital_paise": result.capital_paise,
                "lost_paise": result.lost_paise,
                "mean_balance_notes": round(result.mean_balance_notes, 1),
            }
        )
    return rows
