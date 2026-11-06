"""Outcomes are reproducible and the retry treatment is the one advertised."""

from routelab import data, outcomes, psps


def test_uniform_is_in_range_and_repeatable():
    for index in range(50):
        a = outcomes.uniform(9, index, "alpha", 0)
        assert 0.0 <= a < 1.0
        assert a == outcomes.uniform(9, index, "alpha", 0)


def test_uniform_differs_by_provider_and_attempt():
    a = outcomes.uniform(9, 1, "alpha", 0)
    b = outcomes.uniform(9, 1, "bravo", 0)
    c = outcomes.uniform(9, 1, "alpha", 1)
    assert len({a, b, c}) == 3


def test_a_retry_captures_less_often_than_a_first_attempt():
    txn = data.Txn(1, 5000, "credit", "domestic", "mid")
    first = sum(outcomes.authorizes(5, txn, "alpha", 0, retry=False) for _ in range(1))
    # the draw is fixed per index, so compare the two treatments on a sample
    wins_first = sum(
        outcomes.authorizes(5, data.Txn(i, 5000, "credit", "domestic", "mid"), "alpha", 0, retry=False)
        for i in range(400)
    )
    wins_retry = sum(
        outcomes.authorizes(5, data.Txn(i, 5000, "credit", "domestic", "mid"), "alpha", 0, retry=True)
        for i in range(400)
    )
    assert 0 <= wins_retry < wins_first <= 400
    assert first in (0, 1)


def test_drift_applies_only_after_the_switch_and_only_to_its_token():
    drift = psps.Drift(at=100, psp="bravo", delta=-0.9, token="channel:debit")
    before = data.Txn(99, 5000, "debit", "domestic", "mid")
    after = data.Txn(100, 5000, "debit", "domestic", "mid")
    other = data.Txn(150, 5000, "credit", "domestic", "mid")
    assert drift.shift(before) == 0.0
    assert drift.shift(after) == -0.9
    assert drift.shift(other) == 0.0


def test_a_hard_decline_is_consistent_for_one_key():
    flags = {outcomes.is_hard(2, 17, "charlie", 0) for _ in range(5)}
    assert len(flags) == 1


def test_approval_falls_when_the_provider_is_shifted():
    txn = data.Txn(1, 10000, "credit", "domestic", "mid")
    assert psps.BY_NAME["alpha"].approval(txn, -1.5) < psps.BY_NAME["alpha"].approval(txn)
