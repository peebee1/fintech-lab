"""Policies, tested on views the simulator would hand them."""

from __future__ import annotations

from consent.book import PAY_HOUR
from consent.policy import (
    AdaptiveLead,
    FixedCadence,
    JustInTime,
    NeverRefresh,
    OnFailure,
    View,
    at_risk,
    at_risk_payment,
    is_contextual,
)


def view(**overrides) -> View:
    base = dict(
        pid="T0",
        day=80,
        expiry_h=90 * 24 + 12,
        status="active",
        due_days=(5, 35, 65, 95, 125),
        last_prompt_day=-999,
        observed_max_latency_h=0.0,
        failed_since_prompt=False,
        consent_start=0,
    )
    base.update(overrides)
    return View(**base)


def test_at_risk_is_true_on_and_after_expiry():
    expiry = 95 * 24 + PAY_HOUR
    assert at_risk(expiry, 95) is True
    assert at_risk(expiry, 96) is True
    assert at_risk(expiry, 94) is False


def test_at_risk_payment_names_the_first_uncovered_debit():
    v = view()
    assert at_risk_payment(v, 400) == 95
    assert at_risk_payment(view(day=96), 400) == 125
    assert at_risk_payment(view(expiry_h=10**9), 400) is None


def test_never_refresh_never_prompts():
    assert NeverRefresh().should_prompt(view()) is False


def test_on_failure_waits_for_a_refusal():
    policy = OnFailure()
    assert policy.should_prompt(view(failed_since_prompt=False)) is False
    assert policy.should_prompt(view(failed_since_prompt=True)) is True


def test_fixed_cadence_respects_its_gap():
    policy = FixedCadence(30)
    assert policy.should_prompt(view(day=80, last_prompt_day=60)) is False
    assert policy.should_prompt(view(day=91, last_prompt_day=60)) is True


def test_fixed_cadence_stops_when_nothing_is_left_to_charge():
    assert FixedCadence(30).should_prompt(view(day=200, last_prompt_day=100, due_days=(5, 35))) is False


def test_just_in_time_fires_only_inside_its_lead():
    policy = JustInTime(7)
    assert policy.should_prompt(view(day=80)) is False, "15 days of lead is too much"
    assert policy.should_prompt(view(day=88)) is True, "7 days before an at-risk debit"
    assert policy.should_prompt(view(day=95)) is True, "day of the debit, at risk"


def test_just_in_time_ignores_debits_the_consent_already_covers():
    assert JustInTime(30).should_prompt(view(expiry_h=10**9, day=90)) is False


def test_adaptive_lead_reads_the_customers_own_latency():
    policy = AdaptiveLead()
    assert policy.lead_for(view(observed_max_latency_h=0.0)) == 7
    assert policy.lead_for(view(observed_max_latency_h=50.0)) == 4
    assert policy.lead_for(view(observed_max_latency_h=1.0)) == 2, "floor"
    assert policy.lead_for(view(observed_max_latency_h=400.0)) == 18
    assert policy.lead_for(view(observed_max_latency_h=900.0)) == 21, "ceiling"


def test_context_window_is_inclusive_at_three_days():
    due = (20, 50)
    assert is_contextual(17, due) is True
    assert is_contextual(16, due) is False
    assert is_contextual(50, due) is True
