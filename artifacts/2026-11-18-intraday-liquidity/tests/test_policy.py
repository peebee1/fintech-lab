"""Policies: no lookahead, the stated estimator, and monotone buffers."""

from __future__ import annotations

import dataclasses

import pytest

from liquidity.book import Day, Event
from liquidity.policy import (
    DailyNetMean,
    DailyNetP95,
    GrossBatch,
    Oracle,
    PeakPercentile,
    Zero,
    quantile,
)
from liquidity.sim import required_opening


def test_zero_holds_nothing(book):
    assert Zero().size(book[:50]) == 0


def test_quantile_is_nearest_rank():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert quantile(values, 0.5) == 5
    assert quantile(values, 0.9) == 9
    assert quantile(values, 1.0) == 10
    assert quantile([7], 0.5) == 7
    with pytest.raises(ValueError):
        quantile([], 0.5)
    with pytest.raises(ValueError):
        quantile([1, 2], 0.0)


def test_no_policy_reads_the_day_it_sizes(book):
    """Mutate day i and everything after it. Every buffer must be unchanged."""
    i = 120
    mutated = list(book)
    fake = dataclasses.replace(
        book[i], payout_cents=10**12, first_batch_cents=10**12, events=(Event(660, "payout", 10**12),)
    )
    mutated[i] = fake
    for j in range(i + 1, len(mutated)):
        mutated[j] = dataclasses.replace(mutated[j], payout_cents=10**12)

    for policy in (Zero(), DailyNetMean(), DailyNetP95(), GrossBatch(), PeakPercentile(0.90)):
        assert policy.size(mutated[:i]) == policy.size(book[:i]), policy.name


def test_peak_p100_is_the_trailing_maximum(book):
    window = 40
    policy = PeakPercentile(1.00, window=window)
    history = book[:100]
    assert policy.size(history) == max(required_opening(d) for d in history[-window:])


def test_peak_buffer_uses_only_its_window(book):
    policy = PeakPercentile(0.90, window=20)
    history = book[:100]
    assert policy.size(history) == policy.size(history[-20:])


def test_buffers_rise_with_the_percentile(book):
    sizes = [PeakPercentile(q).size(book[:200]) for q in (0.5, 0.75, 0.9, 0.95, 1.0)]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_gross_batch_is_the_largest_first_batch(book):
    assert GrossBatch(window=20).size(book[:100]) == max(d.first_batch_cents for d in book[80:100])


def test_daily_net_mean_is_the_mean_of_recent_nets(book):
    window = 10
    history = book[:50]
    expected = sum(d.net_cents for d in history[-window:]) // window
    assert DailyNetMean(window=window).size(history) == max(0, expected)


def test_daily_net_p95_never_goes_negative(book):
    for i in range(60, len(book), 37):
        assert DailyNetP95().size(book[:i]) >= 0


def test_oracle_holds_exactly_the_requirement(book):
    for day in book[:60]:
        assert Oracle().size_for(day) == required_opening(day)


def test_empty_history_sizes_zero():
    empty: list[Day] = []
    for policy in (DailyNetMean(), DailyNetP95(), GrossBatch(), PeakPercentile(0.9)):
        assert policy.size(empty) == 0
