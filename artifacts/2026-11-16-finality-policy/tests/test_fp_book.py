"""The book is synthetic, deterministic, and its ids carry no information."""

from collections import Counter

from finality.book import build_book, book_summary
from finality.chain import CHAINS


def test_book_is_deterministic():
    assert build_book(7, days=3) == build_book(7, days=3)


def test_a_different_seed_changes_the_book():
    assert build_book(7, days=3) != build_book(8, days=3)


def test_payments_are_positive_and_integer_minor_units():
    for payment in build_book(11, days=2):
        assert isinstance(payment.amount_cents, int)
        assert payment.amount_cents >= 100
        assert payment.drop_draw >= 0.0


def test_chains_are_declared_and_counts_scale_with_days():
    one_week = build_book(3, days=7)
    two_weeks = build_book(3, days=14)
    counts = Counter(p.chain for p in one_week)
    assert set(counts) == set(CHAINS)
    assert len(two_weeks) == 2 * len(one_week)


def test_ids_do_not_sort_by_chain_or_by_value():
    book = build_book(5, days=7)
    assert [p.pid for p in book] == [f"p{i:05d}" for i in range(len(book))]
    first_chain = book[0].chain
    head = [p.chain for p in book[:20]]
    assert any(chain != first_chain for chain in head)
    amounts = [p.amount_cents for p in book]
    assert amounts != sorted(amounts)


def test_summary_is_plausible_for_the_domain():
    summary = book_summary(build_book(5, days=7))
    assert summary["payments"] == 4000
    assert 50_000 < summary["total_usd"] < 10_000_000
    assert 50 <= summary["median_usd"] <= 500
    assert summary["max_usd"] > summary["p99_usd"] > summary["median_usd"]
