"""Measure an allocation against the book. Pure arithmetic, integer cents."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .book import INSURANCE_CAP_CENTS, LINK_FEE_CENTS, Book, book_stats, generate_book
from .policies import (
    Allocation,
    allocate_capped,
    allocate_even,
    allocate_oracle,
    allocate_yield_only,
)

BPS = 10_000
SWEEP_MAX = 8


@dataclass
class Measured:
    policy: str
    max_links: int
    interest_cents: int
    link_cost_cents: int
    uninsured_cents: int
    exposed_customers: int
    max_customer_links: int
    links: int
    capacity_used_bps: int
    banks_full: int
    top10_customer_interest_cents: int

    @property
    def net_cents(self) -> int:
        return self.interest_cents - self.link_cost_cents

    def to_dict(self, book: Book) -> dict:
        total = book.total_cents
        return {
            "policy": self.policy,
            "max_links": self.max_links,
            "interest_cents": self.interest_cents,
            "blended_apy_bps": self.interest_cents * BPS // total,
            "link_cost_cents": self.link_cost_cents,
            "net_cents": self.net_cents,
            "links": self.links,
            "uninsured_cents": self.uninsured_cents,
            "uninsured_bps": self.uninsured_cents * BPS // total,
            "exposed_customers": self.exposed_customers,
            "max_customer_links": self.max_customer_links,
            "capacity_used_bps": self.capacity_used_bps,
            "banks_full": self.banks_full,
            "top10_customer_interest_cents": self.top10_customer_interest_cents,
        }


def measure(book: Book, alloc: Allocation, link_fee_cents: int = LINK_FEE_CENTS,
            uninsured_top: list[tuple[str, int]] | None = None) -> Measured:
    apy = {b.id: b.apy_bps for b in book.banks}
    capacity = {b.id: b.capacity_cents for b in book.banks}
    by_bank: dict[str, int] = {b.id: 0 for b in book.banks}
    for customer_banks in alloc.rows.values():
        for bank_id, cents in customer_banks.items():
            by_bank[bank_id] += cents

    interest = sum(by_bank[bank_id] * apy[bank_id] // BPS for bank_id in by_bank)

    uninsured = 0
    exposed = 0
    max_links = 0
    for customer in book.customers:
        slices = alloc.rows.get(customer.id, {})
        insured = sum(min(v, INSURANCE_CAP_CENTS) for v in slices.values())
        gap = max(0, customer.balance_cents - insured)
        if gap > 0:
            uninsured += gap
            exposed += 1
            if uninsured_top is not None:
                uninsured_top.append((customer.id, gap))
        max_links = max(max_links, sum(1 for v in slices.values() if v > 0))

    top10 = sum(
        alloc.interest_cents(c.id, apy) for c in book.balances_desc()[:10]
    )
    links = alloc.link_count
    used = sum(by_bank.values())
    banks_full = sum(1 for bid, cents in by_bank.items() if cents >= capacity[bid])
    return Measured(
        policy=alloc.policy,
        max_links=alloc.max_links,
        interest_cents=interest,
        link_cost_cents=links * link_fee_cents,
        uninsured_cents=uninsured,
        exposed_customers=exposed,
        max_customer_links=max_links,
        links=links,
        capacity_used_bps=used * BPS // book.capacity_cents,
        banks_full=banks_full,
        top10_customer_interest_cents=top10,
    )


def one_overflow_at_most(banks: dict[str, int]) -> bool:
    """Covered links sit at the cap. The uncovered remainder may pool at one bank."""
    over = [v for v in banks.values() if v > INSURANCE_CAP_CENTS]
    if not over:
        return True
    return len(over) == 1 and over[0] == max(banks.values())


def capacities_doubled(book: Book) -> Book:
    return replace(
        book,
        banks=tuple(replace(b, capacity_cents=b.capacity_cents * 2) for b in book.banks),
    )


def run(seed: int = 20261128, link_fee_cents: int = LINK_FEE_CENTS,
        customers: int = 1500) -> dict:
    book = generate_book(seed, customers)
    total = book.total_cents

    yield_only = allocate_yield_only(book)
    capped = {k: allocate_capped(book, max_links=k) for k in range(1, SWEEP_MAX + 1)}
    even = allocate_even(book)
    oracle = allocate_oracle(book)

    top: list[tuple[str, int]] = []
    m_yield = measure(book, yield_only, link_fee_cents, top)
    m_capped = {k: measure(book, a, link_fee_cents) for k, a in capped.items()}
    m_even = measure(book, even, link_fee_cents)
    m_oracle = measure(book, oracle, link_fee_cents)

    desc = allocate_capped(book, max_links=3, largest_first=True)
    asc = allocate_capped(book, max_links=3, largest_first=False)
    m_desc = measure(book, desc, link_fee_cents)
    m_asc = measure(book, asc, link_fee_cents)

    wide = capacities_doubled(book)
    m_wide = measure(wide, allocate_capped(wide, max_links=3), link_fee_cents)
    wide_yield = measure(wide, allocate_yield_only(wide), link_fee_cents)

    small_book = generate_book(seed, 60)
    small_yield = measure(small_book, allocate_yield_only(small_book), link_fee_cents)
    small_capped = measure(small_book, allocate_capped(small_book, max_links=3), link_fee_cents)

    top.sort(key=lambda x: (-x[1], x[0]))
    top10 = sum(gap for _, gap in top[:10])
    stats = book_stats(book)
    policies = [m_yield, m_capped[1], m_capped[3], m_even, m_oracle]

    sweep = [{"max_links": k, **m_capped[k].to_dict(book)} for k in range(1, SWEEP_MAX + 1)]

    checks = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check(
        "every cent of every customer is placed",
        all(a.placed(c.id) == c.balance_cents for a in [yield_only, *capped.values(), even, oracle]
            for c in book.customers),
        f"{total} cents placed under every policy",
    )
    check(
        "no bank is over its declared capacity",
        all(
            sum(a.rows.get(c.id, {}).get(b.id, 0) for c in book.customers) <= b.capacity_cents
            for b in book.banks
            for a in [yield_only, capped[3], even, oracle]
        ),
        f"{m_yield.banks_full} of {len(book.banks)} banks full under yield_only",
    )
    check(
        "the capped policies respect the 250,000 cap on every covered link",
        all(one_overflow_at_most(banks) for a in [capped[3], oracle] for banks in a.rows.values()),
        "at most one overflow bank per customer, every other slice at or under 250,000.00",
    )
    check(
        "the capped policy respects its link cap",
        m_capped[3].max_customer_links <= 3,
        f"capped_3 max links per customer {m_capped[3].max_customer_links}",
    )
    check(
        "the insurance cap bites under yield only",
        any(v > INSURANCE_CAP_CENTS for banks in yield_only.rows.values() for v in banks.values()),
        f"{m_yield.uninsured_cents} cents uninsured under yield_only",
    )
    check(
        "the oracle leaves nothing uninsured",
        m_oracle.uninsured_cents == 0,
        f"oracle uninsured {m_oracle.uninsured_cents} cents",
    )
    check(
        "the oracle earns at least the interest of every policy",
        m_oracle.interest_cents >= max(m.interest_cents for m in policies),
        f"oracle {m_oracle.interest_cents} vs yield_only {m_yield.interest_cents}",
    )
    check(
        "interest depends on bank totals, not on customer order",
        m_desc.interest_cents == m_asc.interest_cents,
        f"largest first {m_desc.interest_cents} vs smallest first {m_asc.interest_cents} cents",
    )
    check(
        "insurance within the link cap does not cost interest",
        m_capped[3].interest_cents == m_yield.interest_cents,
        f"capped_3 {m_capped[3].interest_cents} vs yield_only {m_yield.interest_cents} cents",
    )
    check(
        "capacity binds: doubling it raises interest",
        (wide_yield.interest_cents > m_yield.interest_cents
         and m_wide.interest_cents > m_capped[3].interest_cents),
        f"doubled capacity {wide_yield.interest_cents} vs {m_yield.interest_cents} cents",
    )
    check(
        "interest stays under the highest bank rate applied to the whole book",
        m_oracle.interest_cents <= total * max(b.apy_bps for b in book.banks) // BPS,
        f"oracle blended {m_oracle.interest_cents * BPS // total} bps",
    )
    check(
        "the cap costs yield only when the book fits inside the top banks",
        small_capped.interest_cents < small_yield.interest_cents,
        f"small book capped {small_capped.interest_cents} vs yield_only "
        f"{small_yield.interest_cents} cents",
    )

    return {
        "seed": seed,
        "customers": customers,
        "link_fee_cents": link_fee_cents,
        "book": stats,
        "policies": [m.to_dict(book) for m in policies],
        "sweep": sweep,
        "order_sensitivity": {
            "largest_first": m_desc.to_dict(book),
            "smallest_first": m_asc.to_dict(book),
            "interest_delta_cents": m_desc.interest_cents - m_asc.interest_cents,
            "uninsured_delta_cents": m_desc.uninsured_cents - m_asc.uninsured_cents,
            "top10_interest_delta_cents": (
                m_desc.top10_customer_interest_cents - m_asc.top10_customer_interest_cents
            ),
        },
        "capacity_test": {
            "base_interest_cents": m_capped[3].interest_cents,
            "doubled_capacity_interest_cents": m_wide.interest_cents,
            "base_banks_full": m_capped[3].banks_full,
            "doubled_banks_full": m_wide.banks_full,
            "base_capacity_used_bps": m_capped[3].capacity_used_bps,
        },
        "small_book_test": {
            "customers": 60,
            "total_cents": small_book.total_cents,
            "yield_only_interest_cents": small_yield.interest_cents,
            "capped_3_interest_cents": small_capped.interest_cents,
            "yield_delta_cents": small_yield.interest_cents - small_capped.interest_cents,
            "yield_delta_bps_x100": (
                (small_yield.interest_cents - small_capped.interest_cents) * 1_000_000
                // small_book.total_cents
            ),
            "yield_only_links": small_yield.links,
            "capped_3_links": small_capped.links,
            "yield_only_uninsured_cents": small_yield.uninsured_cents,
            "capped_3_uninsured_cents": small_capped.uninsured_cents,
        },
        "uninsured_concentration": {
            "exposed_customers": m_yield.exposed_customers,
            "top10_uninsured_cents": top10,
            "top10_share_bps": top10 * BPS // m_yield.uninsured_cents
            if m_yield.uninsured_cents
            else 0,
        },
        "banks": [
            {
                "id": b.id,
                "apy_bps": b.apy_bps,
                "capacity_cents": b.capacity_cents,
                "allocated_yield_only_cents": sum(
                    yield_only.rows.get(c.id, {}).get(b.id, 0) for c in book.customers
                ),
            }
            for b in book.banks
        ],
        "checks": checks,
    }
