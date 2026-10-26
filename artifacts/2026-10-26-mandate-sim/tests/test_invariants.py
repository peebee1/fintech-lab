import json

import pytest

from mandate.evals import (
    lag_sensitivity,
    reconcile,
    summarise,
    to_markdown,
    to_payload,
)
from mandate.model import CLEAN, EXPOSED, REVERSED
from mandate.sim import PLANNERS, build_population, plan_all, run


@pytest.fixture(scope="module")
def book():
    return build_population(seed=9, subscribers=300)


@pytest.fixture(scope="module")
def measured(book):
    results = plan_all(book)
    return book, results, [summarise(results[pid], book) for pid in PLANNERS]


def test_every_planner_balances(measured):
    _, _, metrics = measured
    for m in metrics:
        ok, notes = reconcile(m)
        assert ok, (m.planner, notes)


def test_invoice_states_can_be_rederived_from_the_attempt_log(book):
    """Second route to the same states: rebuild them from presentations alone."""
    result = run(book, PLANNERS["naive"])
    by_invoice: dict[str, list] = {}
    for attempt in result.attempts:
        by_invoice.setdefault(attempt.invoice_id, []).append(attempt)

    for resolution in result.resolutions:
        attempts = by_invoice.get(resolution.invoice_id, [])
        settled = [a for a in attempts if a.settled]
        if settled:
            expected = (REVERSED, EXPOSED) if settled[0].reasons else (CLEAN,)
            assert resolution.state in expected, resolution.invoice_id
        elif attempts:
            assert resolution.state == "declined", resolution.invoice_id
        else:
            assert resolution.state == "not_presented", resolution.invoice_id


def test_kept_and_landed_identities(measured):
    _, _, metrics = measured
    for m in metrics:
        assert m.kept_minor == m.clean_minor + m.exposed_minor
        assert m.landed_minor == m.kept_minor + m.reversed_minor
        assert m.billed_minor == (
            m.clean_minor
            + m.exposed_minor
            + m.reversed_minor
            + m.declined_minor
            + m.not_presented_minor
        )


def test_cross_rail_rate_is_an_equal_weight_mean(measured):
    _, _, metrics = measured
    for m in metrics:
        rates = [r.kept_bps for r in m.per_rail.values()]
        assert m.mean("kept") == round(sum(rates) / len(rates))


def test_runs_are_reproducible(book):
    first = run(book, PLANNERS["rail_aware"])
    second = run(book, PLANNERS["rail_aware"])
    assert first.attempts == second.attempts
    assert first.resolutions == second.resolutions


def test_the_population_is_reproducible():
    one = build_population(seed=3, subscribers=120)
    two = build_population(seed=3, subscribers=120)
    assert one.invoices == two.invoices
    assert one.claim_draw == two.claim_draw
    assert one.afa_approved == two.afa_approved


def test_no_attempt_is_presented_after_the_horizon(book):
    for planner in PLANNERS.values():
        result = run(book, planner)
        assert max(a.day for a in result.attempts) <= book.horizon_days


def test_exposure_needs_a_lag_window(book):
    rows = lag_sensitivity(book, lags=(0, 3, 7))
    assert rows[0]["exposure_bps"] == 0
    assert rows[-1]["exposure_bps"] > rows[0]["exposure_bps"]


def test_markdown_and_json_are_generated_from_the_run(measured):
    book, _, metrics = measured
    text = to_markdown(metrics, book, lag_sensitivity(book, lags=(0, 1)))
    assert "## Reconciliation" in text
    assert "PASS" in text
    for m in metrics:
        assert m.planner in text

    payload = json.loads(json.dumps(to_payload(metrics, book, lag_sensitivity(book, lags=(0, 1)))))
    assert payload["population"]["invoices"] == len(book.invoices)
    assert len(payload["planners"]) == len(metrics)
    for planner in payload["planners"]:
        assert planner["mean_rates_bps"]["kept"] >= 0
        assert sum(planner["by_state"].values()) == planner["invoices"]


def test_sensitivity_only_changes_exposure_through_the_lag(book):
    rows = lag_sensitivity(book, lags=(0, 7))
    assert rows[0]["reversed_bps"] == 0
    assert rows[0]["kept_bps"] <= rows[1]["kept_bps"]


def test_states_are_mutually_exclusive_and_cover_every_invoice(measured):
    _, _, metrics = measured
    for m in metrics:
        assert set(m.by_state) == {CLEAN, EXPOSED, REVERSED, "declined", "not_presented"}
        assert sum(m.by_state.values()) == m.invoices
