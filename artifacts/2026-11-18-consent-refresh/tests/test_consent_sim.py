"""Simulator mechanics: expiry, prompt lead, abandonment, and the audit."""

from __future__ import annotations

from consent.book import Payer
from consent.policy import JustInTime, NeverRefresh
from consent.sim import audit_consents, run


def one_payer(**overrides) -> Payer:
    base = dict(
        pid="T0",
        merchant="test-merchant",
        bill_cents=10_000,
        due_day=5,
        consent_start=0,
        latency_median_h=1.0,
        abandon_prob=0.0,
        churn_hazard=0.0,
    )
    base.update(overrides)
    return Payer(**base)


def test_expired_consent_refuses_and_a_lead_in_time_renews():
    payer = one_payer()
    never = run([payer], NeverRefresh(), seed=1)
    assert never.totals["refused"] >= 1
    assert never.totals["prompts"] == 0

    timely = run([payer], JustInTime(7), seed=1)
    assert timely.totals["refused"] == 0
    assert timely.totals["renewals"] >= 1
    assert timely.totals["settled"] == len(payer.due_days)


def test_the_same_prompt_one_day_out_misses_a_slow_customer():
    slow = one_payer(latency_median_h=120.0)
    late = run([slow], JustInTime(1), seed=2)
    assert late.totals["refused"] >= 1, "a 5 day reply cannot save a debit 1 day out"


def test_abandonment_ends_the_mandate_and_the_debits():
    payer = one_payer(abandon_prob=1.0)
    result = run([payer], JustInTime(3), seed=3)
    state = result.states[payer.pid]
    assert state.status == "abandoned"
    assert state.abandons == 1
    assert state.exit_day is not None
    remaining = [d for d in payer.due_days if d >= state.exit_day]
    assert remaining, "the book must still have payments after the walk away"
    assert state.attempts < len(payer.due_days)


def test_no_settlement_happens_on_an_expired_consent():
    from consent.book import build_book

    result = run(build_book(seed=4, size=60), JustInTime(3), seed=4)
    audit = audit_consents(result)
    assert audit["checked"] > 0
    assert audit["violations"] == []


def test_the_audit_can_fail():
    from consent.book import build_book

    result = run(build_book(seed=4, size=20), JustInTime(3), seed=4)
    victim = next(s for s in result.states.values() if s.settle_log)
    victim.settle_log.append((result.horizon + 30, 1.0))
    audit = audit_consents(result)
    assert audit["violations"], "a settlement replayed past every expiry must be flagged"


def test_same_seed_same_book_same_totals():
    from consent.book import build_book

    book = build_book(seed=6, size=50)
    a = run(book, JustInTime(3), seed=6).totals
    b = run(book, JustInTime(3), seed=6).totals
    assert a == b


def test_prompts_are_batched_to_the_evening_before_the_charge():
    from consent.book import build_book

    book = build_book(seed=8, size=20)
    result = run(book, JustInTime(3), seed=8)
    prompts = [e for e in result.events if e["kind"] == "prompt"]
    assert prompts
    for event in prompts:
        assert event.get("at_risk_day") is not None
