"""Program bank network for a deposit sweep.

All money is integer cents. No floats touch a balance.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

INSURANCE_CAP_CENTS = 250_000_00
LINK_FEE_CENTS = 150  # one 1099-INT, one statement, one reconciliation per customer and bank


@dataclass(frozen=True)
class Bank:
    id: str
    apy_bps: int
    capacity_cents: int

    @property
    def apy(self) -> float:
        return self.apy_bps / 10_000


@dataclass(frozen=True)
class Customer:
    id: str
    balance_cents: int


@dataclass(frozen=True)
class Book:
    customers: tuple[Customer, ...]
    banks: tuple[Bank, ...]

    @property
    def total_cents(self) -> int:
        return sum(c.balance_cents for c in self.customers)

    @property
    def capacity_cents(self) -> int:
        return sum(b.capacity_cents for b in self.banks)

    def balances_desc(self) -> list[Customer]:
        return sorted(self.customers, key=lambda c: (-c.balance_cents, c.id))

    def balances_asc(self) -> list[Customer]:
        return sorted(self.customers, key=lambda c: (c.balance_cents, c.id))

    def banks_by_yield(self) -> list[Bank]:
        return sorted(self.banks, key=lambda b: (-b.apy_bps, b.id))


BANKS = (
    Bank("bank_1", 455, 3_000_000_00),
    Bank("bank_2", 430, 4_000_000_00),
    Bank("bank_3", 410, 5_000_000_00),
    Bank("bank_4", 395, 6_000_000_00),
    Bank("bank_5", 380, 7_000_000_00),
    Bank("bank_6", 365, 8_000_000_00),
    Bank("bank_7", 350, 10_000_000_00),
    Bank("bank_8", 340, 12_000_000_00),
)


def generate_book(seed: int = 20261128, customers: int = 1500) -> Book:
    """Two tier synthetic retail book: mass market and high balance households.

    The tail exists on purpose. A book of identical balances cannot show what an
    insurance cap does, because no single customer ever reaches it.
    """
    rng = random.Random(seed)
    out: list[Customer] = []
    for i in range(customers):
        if rng.random() < 0.82:
            dollars = rng.lognormvariate(math.log(12_000), 0.85)
        else:
            dollars = rng.lognormvariate(math.log(95_000), 0.55)
        cents = max(int(round(dollars * 100)), 10_000)
        out.append(Customer(f"customer_{i:04d}", cents))
    return Book(tuple(out), BANKS)


def book_stats(book: Book) -> dict:
    balances = sorted(c.balance_cents for c in book.customers)
    n = len(balances)
    total = sum(balances)
    top_n = max(1, n // 20)
    return {
        "customers": n,
        "banks": len(book.banks),
        "total_cents": total,
        "mean_cents": total // n,
        "median_cents": balances[n // 2],
        "max_cents": balances[-1],
        "min_cents": balances[0],
        "top5pct_share_bps": sum(balances[-top_n:]) * 10_000 // total,
        "customers_over_cap": sum(1 for b in balances if b > INSURANCE_CAP_CENTS),
        "capacity_cents": book.capacity_cents,
        "capacity_cover_bps": book.capacity_cents * 10_000 // total,
    }
