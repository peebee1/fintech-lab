"""The central claims: conservation, and the ordering the ladder is supposed to produce."""

import pytest

from cashplan.policies import POLICIES
from cashplan.sim import RATE_BPS, run, sweep_capacity, with_cassettes


@pytest.fixture(scope="module")
def results(book):
    return {policy.name: run(book, policy) for policy in POLICIES}


def test_no_site_day_violates_conservation_or_capacity(results):
    for name, result in results.items():
        assert result.violations == (), name


def test_nothing_is_dispensed_that_was_not_delivered(book, results):
    for result in results.values():
        assert result.dispensed <= book.notes_dispensed()
        assert result.dispensed + result.lost_notes == book.notes_dispensed()


def test_cost_lines_add_up_to_the_total(results):
    for result in results.values():
        assert result.cit_paise + result.capital_paise + result.lost_paise == result.total_paise
        assert result.capital_paise == pytest.approx(
            result.balance_paise_days * RATE_BPS / (10_000 * 365), rel=1e-9, abs=1
        )


def test_the_oracle_serves_everything(results):
    oracle = results["oracle_minmax"]
    assert oracle.service_level == 1.0
    assert oracle.lost_withdrawals == 0


def test_the_default_weekly_fill_runs_dry_somewhere(results):
    weekly = results["fixed_week_capacity"]
    assert weekly.service_level < 1.0
    assert weekly.lost_withdrawals > 0


def test_same_trips_less_cash_is_a_bad_trade(results):
    """Cutting the fill quantity without adding trips lowers cash but breaks service."""
    weekly = results["fixed_week_capacity"]
    trimmed = results["fixed_week_cover"]
    assert trimmed.visits == weekly.visits
    assert trimmed.mean_balance_notes < weekly.mean_balance_notes
    assert trimmed.service_level < weekly.service_level - 0.02


def test_fewer_trips_is_the_most_expensive_rung(results):
    fortnight = results["fixed_fortnight_cover"]
    weekly = results["fixed_week_capacity"]
    assert fortnight.visits < weekly.visits
    assert fortnight.cit_paise < weekly.cit_paise
    assert fortnight.total_paise > weekly.total_paise


def test_the_minmax_policy_beats_the_weekly_full_fill(results):
    best = results["minmax_3_6"]
    weekly = results["fixed_week_capacity"]
    assert best.total_paise < weekly.total_paise
    assert best.service_level >= weekly.service_level


def test_the_oracle_is_the_cheapest_reference(results):
    oracle = results["oracle_minmax"]
    for name, result in results.items():
        if name != "oracle_minmax":
            assert oracle.total_paise < result.total_paise


def test_the_oracle_trades_trips_for_cash(results):
    oracle = results["oracle_minmax"]
    best = results["minmax_3_6"]
    assert oracle.visits > best.visits
    assert oracle.cit_paise > best.cit_paise
    assert oracle.capital_paise < best.capital_paise


def test_capacity_sweep_changes_capacity_and_nothing_else(book):
    resized = with_cassettes(book, 5)
    assert [s.capacity for s in resized.sites] == [12_500 for _ in resized.sites]
    assert resized.notes_dispensed() == book.notes_dispensed()
    assert resized.withdrawals() == book.withdrawals()


def test_a_fixed_cadence_makes_capacity_bind(book):
    rows = sweep_capacity(book, next(p for p in POLICIES if p.name == "fixed_week_capacity"))
    services = [row["service_level"] for row in rows]
    assert services[0] < 0.85
    assert services[-1] > 0.999
    assert services == sorted(services)


def test_a_daily_cadence_makes_capacity_cheap_to_add(book):
    rows = sweep_capacity(book, next(p for p in POLICIES if p.name == "minmax_3_6"))
    assert all(row["service_level"] == 1.0 for row in rows)
    totals = [row["total_paise"] for row in rows]
    assert totals[0] > totals[2]
