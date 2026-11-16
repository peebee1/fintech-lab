"""One payment, two clocks. The statuses are what the README claims they are."""

from finality.book import Payment
from finality.chain import Reorg
from finality.sim import evaluate, index, metrics, percentile


def payment(**overrides) -> Payment:
    base = dict(
        pid="p00001",
        chain="base",
        amount_cents=14_000,
        arrival_s=200,
        inclusion_height=100,
        drop_draw=0.10,
    )
    base.update(overrides)
    return Payment(**base)


def test_no_reorg_credits_at_the_chosen_height():
    out = evaluate(payment(), index([]), k=4, drop_prob=0.55)
    assert out.status == "ok"
    assert out.credit_height == 103
    assert out.delay_s == 103 * 2 - 200
    assert out.loss_cents == 0
    assert out.exposed_cents == 0


def test_a_deep_fork_that_is_not_yet_visible_loses_the_payment():
    # Fork 10 blocks back, 15 deep: the replacement branch only becomes visible at
    # height 104, after a 1 block credit at height 100.
    reorg = Reorg("base", 90, 15)
    out = evaluate(payment(drop_draw=0.10), index([reorg]), k=1, drop_prob=0.55)
    assert out.status == "lost"
    assert out.loss_cents == 14_000
    assert out.exposed_cents == 14_000


def test_waiting_past_detection_turns_the_loss_into_a_delay():
    reorg = Reorg("base", 90, 15)
    out = evaluate(payment(), index([reorg]), k=5, drop_prob=0.55)
    assert out.status == "held"
    assert out.loss_cents == 0
    assert out.exposed_cents == 0
    assert out.credit_height == 104 + 1 + 5


def test_the_same_payment_is_still_lost_just_below_detection():
    reorg = Reorg("base", 90, 15)
    out = evaluate(payment(), index([reorg]), k=3, drop_prob=0.55)
    assert out.status == "lost"


def test_a_reincluded_payment_is_exposure_without_a_loss():
    reorg = Reorg("base", 90, 15)
    out = evaluate(payment(drop_draw=0.90), index([reorg]), k=1, drop_prob=0.55)
    assert out.status == "reverted"
    assert out.loss_cents == 0
    assert out.exposed_cents == 14_000


def test_a_reorg_that_forks_after_the_block_does_not_reach_it():
    out = evaluate(payment(), index([Reorg("base", 101, 40)]), k=1, drop_prob=0.55)
    assert out.status == "ok"


def test_a_reorg_on_another_chain_is_irrelevant():
    out = evaluate(
        payment(), index([Reorg("ethereum", 90, 50)]), k=1, drop_prob=0.55
    )
    assert out.status == "ok"


def test_credit_is_never_before_inclusion():
    reorg = Reorg("base", 90, 15)
    for k in (1, 2, 5, 20):
        out = evaluate(payment(), index([reorg]), k=k, drop_prob=0.55)
        assert out.credit_height >= 100


def test_metrics_reconcile_with_the_outcomes():
    reorg = Reorg("base", 90, 15)
    idx = index([reorg])
    outcomes = [
        evaluate(payment(pid="a", drop_draw=0.1), idx, k=1, drop_prob=0.55),
        evaluate(payment(pid="b", drop_draw=0.9), idx, k=1, drop_prob=0.55),
        evaluate(payment(pid="c"), idx, k=6, drop_prob=0.55),
    ]
    row = metrics(outcomes)
    assert row["payments"] == 3
    assert row["false_credits"] == 2
    assert row["loss_usd"] == 140.0
    assert row["exposed_usd"] == 280.0
    assert row["loss_usd"] <= row["exposed_usd"]
    assert row["total_cost_usd"] >= row["loss_usd"]


def test_percentile_handles_the_edges():
    assert percentile([], 0.5) == 0.0
    assert percentile([5], 0.95) == 5.0
    assert percentile([1, 2, 3, 4], 0.5) == 2.0
    assert percentile([1, 2, 3, 4], 1.0) == 4.0
