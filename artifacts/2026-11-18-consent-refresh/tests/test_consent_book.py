"""The book has to be a plausible subscription book before anything else is believable."""

from __future__ import annotations

from consent.book import HORIZON_DAYS, MONTH_DAYS, annual_value_cents, build_book


def test_identical_seeds_build_identical_books():
    assert build_book(seed=11, size=25) == build_book(seed=11, size=25)
    assert build_book(seed=11, size=25) != build_book(seed=12, size=25)


def test_schedule_is_monthly_on_one_day():
    book = build_book(seed=3, size=60)
    for payer in book:
        assert len(payer.due_days) == len(set(payer.due_days))
        assert all(d % MONTH_DAYS == payer.due_day for d in payer.due_days)
        assert all(payer.consent_start <= d < HORIZON_DAYS for d in payer.due_days)
        assert 1 <= len(payer.due_days) <= 12


def test_bills_and_latencies_are_in_a_plausible_range():
    book = build_book(seed=5, size=300)
    bills = sorted(p.bill_cents for p in book)
    median = bills[len(bills) // 2]
    assert 2_000 <= median <= 5_000, "median subscription bill should be tens of dollars"
    assert bills[0] >= 500 and bills[-1] <= 40_000
    assert all(1.0 <= p.latency_median_h <= 400.0 for p in book)
    assert all(0.0 < p.abandon_prob < 0.5 for p in book)
    assert all(0.0 < p.churn_hazard < 0.1 for p in book)


def test_annual_value_matches_the_schedule():
    book = build_book(seed=9, size=80)
    expected = sum(p.bill_cents * len(p.due_days) for p in book)
    assert annual_value_cents(book) == expected
    assert annual_value_cents(book) > 0


def test_a_late_consent_start_loses_its_earlier_payments():
    book = build_book(seed=9, size=120)
    for payer in book:
        if payer.consent_start > 0:
            assert all(d >= payer.consent_start for d in payer.due_days)
