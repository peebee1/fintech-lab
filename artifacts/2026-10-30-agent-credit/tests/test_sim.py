import pytest

from creditnet import sim
from creditnet.credit import GROSS, NET, RULES, UNLIMITED


@pytest.fixture(scope="module")
def payload() -> dict:
    return sim.experiments()


def test_market_is_deterministic() -> None:
    first = sim.market(3)
    second = sim.market(3)
    assert first == second
    assert len(first) == sim.TARGET_OBLIGATIONS


def test_market_has_no_self_payments_and_positive_amounts() -> None:
    for obligation in sim.market(5):
        assert obligation.payer != obligation.payee
        assert obligation.amount > 0


def test_market_differs_by_seed() -> None:
    assert sim.market(1, seed=1) != sim.market(1, seed=2)


def test_every_rule_leaves_balanced_books(payload: dict) -> None:
    assert payload["netting"]["all_windows_balanced"] is True
    for row in payload["windows"]:
        assert row["imbalance"] == 0


def test_netting_is_ordered_gross_bilateral_multilateral(payload: dict) -> None:
    for row in payload["windows"]:
        assert row["multilateral_value"] <= row["bilateral_value"] <= row["gross_value"]
        assert 0.0 <= row["reduction_pct"] <= 100.0


def test_reduction_is_large_and_reported(payload: dict) -> None:
    netting = payload["netting"]
    assert netting["multilateral_reduction_pct"] > 90.0
    assert netting["bilateral_reduction_pct"] < netting["multilateral_reduction_pct"]
    assert netting["gross_value"] > netting["bilateral_value"] > netting["multilateral_value"]


def test_net_cap_never_breaches_its_limit(payload: dict) -> None:
    for entry in payload["sweep"]:
        limit = entry["limit"]
        assert entry["rules"][NET]["worst_default_loss"] <= limit
        assert entry["rules"][GROSS]["worst_default_loss"] <= limit


def test_net_cap_carries_more_flow_than_the_gross_cap(payload: dict) -> None:
    for entry in payload["sweep"]:
        net_share = entry["rules"][NET]["admitted_share_pct"]
        gross_share = entry["rules"][GROSS]["admitted_share_pct"]
        assert net_share >= gross_share
        assert entry["rules"][NET]["admitted_value"] >= entry["rules"][GROSS]["admitted_value"]


def test_the_tight_limit_still_throttles_the_gross_rule(payload: dict) -> None:
    tight = payload["sweep"][0]
    assert tight["rules"][GROSS]["admitted_share_pct"] < 50.0
    assert tight["rules"][NET]["admitted_share_pct"] > 90.0


def test_unlimited_is_the_only_rule_that_can_run_past_the_limit(payload: dict) -> None:
    unlimited_over = sum(
        entry["rules"][UNLIMITED]["windows_over_limit"] for entry in payload["sweep"]
    )
    capped_over = sum(
        entry["rules"][rule]["windows_over_limit"]
        for entry in payload["sweep"]
        for rule in (GROSS, NET)
    )
    assert unlimited_over > 0
    assert capped_over == 0


def test_close_out_ratio_is_above_one(payload: dict) -> None:
    """The defaulting agent sends more gross than it owes net, which is the netting bet."""
    assert payload["default"]["mean_close_out_ratio"] > 1.0
    assert payload["default"]["limit_covers_worst_loss"] is True


def test_every_window_offers_the_same_shape(payload: dict) -> None:
    for row in payload["windows"]:
        assert row["offered"] == sim.TARGET_OBLIGATIONS
        assert row["gross_value"] > 0


def test_victim_is_a_member_with_a_net_obligation() -> None:
    record = sim.window(0, sim.REFERENCE_LIMIT)
    assert record["victim"] in sim.member_names()
    assert record["victim_net_debit"] > 0
    assert record["victim_gross_outflow"] >= record["victim_net_debit"]


def test_experiments_are_reproducible() -> None:
    assert sim.experiments(scenarios=3) == sim.experiments(scenarios=3)


def test_every_rule_appears_in_every_sweep_entry(payload: dict) -> None:
    for entry in payload["sweep"]:
        assert tuple(entry["rules"]) == RULES
    assert len(payload["sweep"]) == len(sim.LIMITS)
