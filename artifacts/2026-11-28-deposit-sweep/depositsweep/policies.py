"""Allocation policies. A policy is a pure function of the book, nothing else.

Every policy places every cent: money that cannot be insured within the link cap is
swept into the highest yield bank with room and counted as uninsured. Money does not
evaporate, it stops being covered.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .book import INSURANCE_CAP_CENTS, Book

DEFAULT_MAX_LINKS = 3
ORACLE_LINKS = 12


@dataclass
class Allocation:
    policy: str
    max_links: int
    rows: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, customer_id: str, bank_id: str, cents: int) -> None:
        self.rows.setdefault(customer_id, {})
        self.rows[customer_id][bank_id] = self.rows[customer_id].get(bank_id, 0) + cents

    def placed(self, customer_id: str) -> int:
        return sum(self.rows.get(customer_id, {}).values())

    def links(self, customer_id: str) -> int:
        return sum(1 for v in self.rows.get(customer_id, {}).values() if v > 0)

    def interest_cents(self, customer_id: str, apy: dict[str, int]) -> int:
        return sum(v * apy[bank_id] // 10_000 for bank_id, v in self.rows.get(customer_id, {}).items())

    @property
    def link_count(self) -> int:
        return sum(1 for banks in self.rows.values() for v in banks.values() if v > 0)


def _sweep_residual(alloc: Allocation, banks, remaining: dict[str, int],
                    customer_id: str, residual: int, used: set[str] | None = None) -> None:
    """Place money that the link cap or the insurance cap could not cover.

    Banks the customer already has a link at come first: opening a new bank to
    hold uninsured overflow would break the link cap for no insurance gain.
    """
    order = [b for b in banks if used and b.id in used] + [b for b in banks if not used or b.id not in used]
    for bank in order:
        if residual <= 0:
            return
        take = min(residual, remaining[bank.id])
        if take > 0:
            alloc.add(customer_id, bank.id, take)
            remaining[bank.id] -= take
            residual -= take


def allocate_yield_only(book: Book) -> Allocation:
    """Optimise yield and treat deposits as fungible: the common default.

    The $250,000 insurance cap is not consulted, because nothing in a yield
    optimiser records it as a constraint. That is the defect this policy prices.
    """
    banks = book.banks_by_yield()
    remaining = {b.id: b.capacity_cents for b in banks}
    alloc = Allocation("yield_only", 1)
    for customer in book.balances_desc():
        residual = customer.balance_cents
        for bank in banks:
            if residual <= 0:
                break
            take = min(residual, remaining[bank.id])
            if take > 0:
                alloc.add(customer.id, bank.id, take)
                remaining[bank.id] -= take
                residual -= take
    return alloc


def allocate_capped(
    book: Book,
    max_links: int = DEFAULT_MAX_LINKS,
    largest_first: bool = True,
) -> Allocation:
    """Fill each customer up to the cap per bank, at most max_links banks.

    Whatever is left after max_links banks is swept into the next bank with room
    without the cap, so it is placed but uninsured. Largest balance first spends
    the scarce links on the customers who need them.
    """
    banks = book.banks_by_yield()
    remaining = {b.id: b.capacity_cents for b in banks}
    alloc = Allocation(f"capped_{max_links}", max_links)
    customers = book.balances_desc() if largest_first else book.balances_asc()
    for customer in customers:
        residual = customer.balance_cents
        links = 0
        used: set[str] = set()
        for bank in banks:
            if residual <= 0 or links >= max_links:
                break
            if remaining[bank.id] <= 0 or bank.id in used:
                continue
            take = min(residual, INSURANCE_CAP_CENTS, remaining[bank.id])
            if take > 0:
                alloc.add(customer.id, bank.id, take)
                remaining[bank.id] -= take
                residual -= take
                links += 1
                used.add(bank.id)
        if residual > 0:
            _sweep_residual(alloc, banks, remaining, customer.id, residual, used)
    return alloc


def allocate_even(book: Book) -> Allocation:
    """Split every balance equally across all banks. The naive diversification."""
    banks = book.banks_by_yield()
    remaining = {b.id: b.capacity_cents for b in banks}
    alloc = Allocation("even", len(banks))
    share_div = len(banks)
    for customer in book.balances_desc():
        share = customer.balance_cents // share_div
        residual = customer.balance_cents
        for bank in banks:
            if residual <= 0:
                break
            take = min(share, residual, remaining[bank.id])
            if take > 0:
                alloc.add(customer.id, bank.id, take)
                remaining[bank.id] -= take
                residual -= take
        if residual > 0:
            _sweep_residual(alloc, banks, remaining, customer.id, residual)
    return alloc


def allocate_oracle(book: Book) -> Allocation:
    """Enough links that every customer can reach the cap. The network's ceiling."""
    return allocate_capped(book, max_links=ORACLE_LINKS)
