"""The bench reproduces byte for byte, every control bites, and the claim holds."""

import json

import pytest

from finality import bench


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    return bench.run_bench(tmp_path_factory.mktemp("bench"))


def test_two_runs_are_byte_identical(tmp_path):
    bench.run_bench(tmp_path / "one")
    bench.run_bench(tmp_path / "two")
    for name in ("summary.json", "summary.md"):
        assert (tmp_path / "one" / name).read_bytes() == (
            tmp_path / "two" / name
        ).read_bytes()


def test_all_checks_pass(payload):
    failed = [name for name, ok in payload["checks"].items() if not ok]
    assert failed == []


def test_crediting_on_inclusion_loses_money(payload):
    assert payload["policies"]["credit_on_inclusion"]["loss_usd"] > 0
    assert payload["policies"]["credit_on_inclusion"]["loss_bps"] > 50


def test_fixed_twelve_cuts_the_loss_but_does_not_remove_it(payload):
    quick = payload["policies"]["credit_on_inclusion"]["loss_usd"]
    fixed = payload["policies"]["fixed_12"]["loss_usd"]
    assert fixed > 0
    assert fixed < quick / 3


def test_ticket_tiers_beat_both_fixed_counts(payload):
    fixed = payload["policies"]["fixed_12"]["loss_usd"]
    tiers = payload["policies"]["ticket_tiers"]["loss_usd"]
    defaults = payload["policies"]["chain_defaults"]["loss_usd"]
    assert tiers < fixed / 3
    assert tiers < defaults / 3


def test_the_tiered_rule_keeps_most_payments_inside_a_minute(payload):
    row = payload["policies"]["ticket_tiers"]
    assert row["share_credited_60s"] > 0.85
    assert row["loss_bps"] < 6


def test_the_fitted_curve_has_the_lowest_cost_in_distribution(payload):
    rows = payload["policies"]
    assert rows["calibrated"]["total_cost_usd"] == min(
        row["total_cost_usd"] for row in rows.values()
    )
    assert rows["calibrated"]["loss_usd"] < rows["ticket_tiers"]["loss_usd"]


def test_the_fitted_curve_is_not_robust_to_a_deeper_tail(payload):
    stress = payload["stress"]["policies"]
    assert payload["stress"]["incident_scale"] > 1.0
    assert stress["calibrated"]["loss_usd"] > payload["policies"]["calibrated"]["loss_usd"] * 5
    assert stress["ticket_tiers"]["loss_usd"] < stress["fixed_12"]["loss_usd"]


def test_the_loss_curve_never_rises_with_confirmations(payload):
    for chain, curve in payload["risk"]["loss"].items():
        assert all(a >= b for a, b in zip(curve, curve[1:])), chain
        assert curve[0] > 0, chain


def test_the_sweep_shows_the_cliff(payload):
    rows = {row["k"]: row for row in payload["sweep"]}
    assert rows[1]["loss_usd"] > rows[12]["loss_usd"] > rows[32]["loss_usd"]
    assert rows[48]["loss_usd"] == 0
    assert rows[48]["median_delay_s"] > rows[12]["median_delay_s"]


def test_every_week_is_scored(payload):
    for name, row in payload["policies"].items():
        assert len(row["per_week"]) == len(payload["weeks"]) == 4, name
        assert all(week["loss_usd"] >= 0 for week in row["per_week"])


def test_committed_results_match_a_fresh_run(payload, artifact_dir):
    committed = json.loads((artifact_dir / "results" / "summary.json").read_text())
    assert committed["policies"] == payload["policies"]
    assert committed["sweep"] == payload["sweep"]
    assert committed["stress"] == payload["stress"]
