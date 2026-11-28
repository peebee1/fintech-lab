"""Allocation: the invariants the README leans on, on a hand built book first."""

import pytest

from depositsweep.bench import capacities_doubled, measure, one_overflow_at_most
from depositsweep.book import INSURANCE_CAP_CENTS, Bank, Book, Customer, generate_book
from depositsweep.policies import (
    allocate_capped,
    allocate_even,
    allocate_oracle,
    allocate_yield_only,
)

TINY = Book(
    customers=(Customer("c1", 40_000_000),),  # 400,000.00
    banks=(
        Bank("a", 500, 100_000_000),  # 1,000,000.00 at 5.00 percent
        Bank("b", 400, 100_000_000),  # 1,000,000.00 at 4.00 percent
    ),
)


def test_yield_only_puts_the_whole_balance_in_the_best_bank():
    alloc = allocate_yield_only(TINY)
    assert alloc.rows["c1"] == {"a": 40_000_000}


def test_yield_only_interest_and_uninsured_are_exact():
    m = measure(TINY, allocate_yield_only(TINY))
    assert m.interest_cents == 2_000_000  # 400,000 at 5.00 percent
    assert m.uninsured_cents == 15_000_000  # 400,000 minus the 250,000 cap
    assert m.links == 1


def test_capping_splits_at_the_cap_and_prices_the_difference():
    m = measure(TINY, allocate_capped(TINY, max_links=2))
    assert m.uninsured_cents == 0
    assert m.links == 2
    # 250,000 at 5.00 percent plus 150,000 at 4.00 percent
    assert m.interest_cents == 1_250_000 + 600_000


def test_even_split_is_insured_here_and_earns_less_than_the_capped_split():
    even = measure(TINY, allocate_even(TINY))
    capped = measure(TINY, allocate_capped(TINY, max_links=2))
    assert even.uninsured_cents == 0
    assert even.interest_cents == 1_000_000 + 800_000
    assert even.interest_cents < capped.interest_cents


def test_the_oracle_matches_the_capped_split_on_a_book_it_can_cover():
    assert measure(TINY, allocate_oracle(TINY)).interest_cents == measure(
        TINY, allocate_capped(TINY, max_links=2)
    ).interest_cents


def test_one_overflow_at_most_helper():
    assert one_overflow_at_most({"a": INSURANCE_CAP_CENTS, "b": 1})
    assert one_overflow_at_most({"a": INSURANCE_CAP_CENTS + 500, "b": 1})
    assert not one_overflow_at_most({"a": INSURANCE_CAP_CENTS + 500, "b": INSURANCE_CAP_CENTS + 1})


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_cent_is_placed_and_no_bank_breaks_capacity(seed):
    book = generate_book(seed, 200)
    for alloc in [
        allocate_yield_only(book),
        allocate_capped(book, 3),
        allocate_even(book),
        allocate_oracle(book),
    ]:
        for customer in book.customers:
            assert alloc.placed(customer.id) == customer.balance_cents
        for bank in book.banks:
            held = sum(alloc.rows.get(c.id, {}).get(bank.id, 0) for c in book.customers)
            assert held <= bank.capacity_cents


@pytest.mark.parametrize("k", [2, 3, 4])
def test_the_link_cap_holds(k):
    book = generate_book()
    alloc = allocate_capped(book, max_links=k)
    assert max(alloc.links(c.id) for c in book.customers) <= k


def test_a_one_link_cap_only_breaks_where_the_bank_is_full():
    """A customer cannot stay inside one link if that bank has no capacity left."""
    book = generate_book()
    alloc = allocate_capped(book, max_links=1)
    held = {
        bank.id: sum(alloc.rows.get(c.id, {}).get(bank.id, 0) for c in book.customers)
        for bank in book.banks
    }
    capacity = {bank.id: bank.capacity_cents for bank in book.banks}
    apy = {bank.id: bank.apy_bps for bank in book.banks}
    for customer in book.customers:
        banks = alloc.rows.get(customer.id, {})
        if len(banks) > 1:
            first = max(banks, key=lambda bid: (apy[bid], bid))
            assert held[first] == capacity[first]


@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_capped_policies_keep_every_covered_link_at_the_cap(k):
    book = generate_book()
    alloc = allocate_capped(book, max_links=k)
    for banks in alloc.rows.values():
        assert one_overflow_at_most(banks)


def test_more_links_never_leave_more_uninsured():
    book = generate_book()
    totals = [measure(book, allocate_capped(book, k)).uninsured_cents for k in range(1, 6)]
    assert totals == sorted(totals, reverse=True)


def test_four_links_cover_the_largest_balance_in_this_book():
    book = generate_book()
    assert measure(book, allocate_capped(book, 4)).uninsured_cents == 0


def test_capping_three_links_beats_yield_only_on_uninsured_dollars():
    book = generate_book()
    yield_only = measure(book, allocate_yield_only(book))
    capped = measure(book, allocate_capped(book, 3))
    assert yield_only.uninsured_cents > capped.uninsured_cents > 0


def test_interest_is_the_same_for_every_policy_because_capacity_binds():
    book = generate_book()
    interests = {
        m.interest_cents
        for m in [
            measure(book, allocate_yield_only(book)),
            measure(book, allocate_capped(book, 3)),
            measure(book, allocate_even(book)),
            measure(book, allocate_oracle(book)),
        ]
    }
    assert len(interests) == 1


def test_doubling_capacity_raises_interest_so_capacity_really_binds():
    book = generate_book()
    wide = capacities_doubled(book)
    assert measure(wide, allocate_yield_only(wide)).interest_cents > measure(
        book, allocate_yield_only(book)
    ).interest_cents


def test_order_moves_who_is_insured_and_not_the_total_interest():
    book = generate_book()
    big_first = measure(book, allocate_capped(book, 3, largest_first=True))
    small_first = measure(book, allocate_capped(book, 3, largest_first=False))
    assert big_first.interest_cents == small_first.interest_cents
    assert big_first.uninsured_cents < small_first.uninsured_cents
