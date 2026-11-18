"""The book: determinism, internal consistency, and the two counterfactuals."""

from __future__ import annotations

from liquidity.book import (
    EARLY_SETTLEMENT_MINUTE,
    LATE_SETTLEMENT_MINUTE,
    PAYOUT_ONE_MINUTE,
    PAYOUT_TWO_MINUTE,
    BookParams,
    book_totals,
    build_book,
)

SEED = 20261118


def test_same_seed_same_book():
    assert build_book(SEED) == build_book(SEED)


def test_different_seed_different_book():
    assert build_book(SEED)[:40] != build_book(SEED + 1)[:40]


def test_a_days_events_add_up_to_its_own_totals(book):
    for day in book:
        inflows = sum(e.cents for e in day.events if e.kind == "inflow")
        payouts = sum(e.cents for e in day.events if e.kind == "payout")
        assert inflows == day.inflow_cents
        assert payouts == day.payout_cents
        assert day.net_cents == day.inflow_cents - day.payout_cents
        assert day.first_batch_cents + day.second_batch_cents == day.payout_cents


def test_events_are_in_time_order_with_the_four_moments(book):
    for day in book:
        minutes = [e.minute for e in day.events]
        assert minutes == sorted(minutes)
        assert EARLY_SETTLEMENT_MINUTE in minutes
        assert LATE_SETTLEMENT_MINUTE in minutes
        # The payouts leave before the late settlement lands. That is the thesis.
        assert PAYOUT_ONE_MINUTE < PAYOUT_TWO_MINUTE < LATE_SETTLEMENT_MINUTE


def test_every_payout_is_positive(book):
    for day in book[:120]:
        assert day.first_batch_cents > 0
        assert day.second_batch_cents > 0


def test_book_is_break_even_on_a_daily_view(book):
    totals = book_totals(book)
    # Net flow is noise around zero on purpose: on a daily view this account
    # needs no buffer at all, which is exactly why the daily view is wrong here.
    assert abs(totals["net_cents"]) < 0.01 * totals["payout_cents"]
    assert 0.4 < totals["net_positive_days"] / totals["days"] < 0.6


def test_retimed_settlement_keeps_the_same_payouts():
    """The schedule experiment must not quietly change the book it compares."""
    base = build_book(SEED, BookParams(days=200))
    retimed = build_book(SEED, BookParams(days=200, all_in_at_open=True))
    assert [d.payout_cents for d in base] == [d.payout_cents for d in retimed]
    assert [d.card_cents for d in base] == [d.card_cents for d in retimed]
    assert all(d.late_inflow_cents == 0 for d in retimed)
    assert all(d.early_inflow_cents > 0 for d in retimed)


def test_volume_jump_lands_on_the_stated_day():
    base = build_book(SEED, BookParams(days=120))
    jumped = build_book(SEED, BookParams(days=120, jump_at=60, jump_mult=1.25))
    assert [d.card_cents for d in base[:60]] == [d.card_cents for d in jumped[:60]]
    ratio = sum(d.card_cents for d in jumped[60:]) / sum(d.card_cents for d in base[60:])
    assert 1.2 < ratio < 1.3
