"""The book: deterministic, synthetic, and shaped so the cap has something to bind on."""

from depositsweep.book import INSURANCE_CAP_CENTS, book_stats, generate_book


def test_same_seed_same_book():
    a = generate_book(7, 50)
    b = generate_book(7, 50)
    assert [c.balance_cents for c in a.customers] == [c.balance_cents for c in b.customers]
    assert a.total_cents == b.total_cents


def test_a_different_seed_draws_a_different_book():
    a = generate_book(7, 50)
    b = generate_book(8, 50)
    assert a.total_cents != b.total_cents


def test_every_balance_is_a_positive_integer_number_of_cents():
    book = generate_book()
    assert all(isinstance(c.balance_cents, int) and c.balance_cents > 0 for c in book.customers)


def test_the_book_total_is_the_sum_of_the_balances():
    book = generate_book()
    assert book.total_cents == sum(c.balance_cents for c in book.customers)


def test_no_duplicate_customer_ids():
    book = generate_book()
    ids = [c.id for c in book.customers]
    assert len(ids) == len(set(ids))


def test_the_book_has_a_tail_above_the_cap():
    """Without a tail over 250,000 the insurance cap cannot change any allocation."""
    stats = book_stats(generate_book())
    assert stats["max_cents"] > INSURANCE_CAP_CENTS
    assert stats["customers_over_cap"] >= 1


def test_capacity_covers_the_book_but_not_by_much():
    """Capacity is meant to bind. A network with double the deposits proves nothing."""
    book = generate_book()
    assert book.capacity_cents > book.total_cents
    assert book.capacity_cents < book.total_cents * 12 // 10


def test_stats_shares_are_bounded():
    stats = book_stats(generate_book())
    assert 0 < stats["top5pct_share_bps"] < 10_000
    assert stats["median_cents"] <= stats["mean_cents"] <= stats["max_cents"]
