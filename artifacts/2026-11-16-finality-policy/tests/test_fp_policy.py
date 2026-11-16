"""Policies: one number, one number per chain, a table by ticket, a fitted curve."""

import pytest

from finality.book import Payment
from finality.chain import CHAINS
from finality.cost import Params, delay_cost_usd
from finality.policy import (
    MAX_K,
    POLICIES,
    chain_defaults,
    clamps,
    credit_on_inclusion,
    economic_k,
    fixed_12,
    seconds_to_blocks,
    ticket_tiers,
)

PARAMS = Params()


def make(chain: str = "base", amount_usd: float = 100.0) -> Payment:
    return Payment(
        pid="p00001",
        chain=chain,
        amount_cents=int(amount_usd * 100),
        arrival_s=0,
        inclusion_height=10,
        drop_draw=0.5,
    )


def risk_table(loss: dict[str, float], max_k: int = MAX_K) -> dict:
    return {
        "loss": {name: [loss.get(name, 0.0)] * max_k for name in CHAINS},
        "false_credit": {name: [0.0] * max_k for name in CHAINS},
    }


def test_credit_on_inclusion_is_one_block_everywhere():
    for chain in CHAINS:
        assert credit_on_inclusion(make(chain), {}, PARAMS) == 1


def test_fixed_twelve_ignores_chain_and_ticket():
    assert fixed_12(make("base", 10), {}, PARAMS) == 12
    assert fixed_12(make("ethereum", 90_000), {}, PARAMS) == 12


def test_chain_defaults_are_stable_and_differ_by_chain():
    assert chain_defaults(make("base"), {}, PARAMS) == 12
    assert chain_defaults(make("polygon"), {}, PARAMS) == 30
    assert chain_defaults(make("ethereum"), {}, PARAMS) == 32


def test_seconds_to_blocks_converts_per_chain():
    assert seconds_to_blocks(12, "base") == 6
    assert seconds_to_blocks(12, "ethereum") == 1
    assert seconds_to_blocks(0.5, "ethereum") == 1


def test_ticket_tiers_never_shrink_as_the_ticket_grows():
    previous = 0
    for amount in (10, 99, 100, 999, 1000, 9_999, 10_000, 100_000):
        k = ticket_tiers(make("base", amount), {}, PARAMS)
        assert k >= previous
        previous = k
    assert ticket_tiers(make("base", 100_000), {}, PARAMS) >= ticket_tiers(
        make("base", 10), {}, PARAMS
    )


def test_ticket_tiers_cap_at_max_k():
    for chain in CHAINS:
        assert 1 <= ticket_tiers(make(chain, 500_000), {}, PARAMS) <= MAX_K


def test_every_policy_returns_a_usable_depth():
    risk = risk_table({"base": 1e-4})
    for name in POLICIES:
        for chain in CHAINS:
            for amount in (5, 500, 50_000):
                k = POLICIES[name](make(chain, amount), risk, PARAMS)
                assert 1 <= k <= MAX_K, (name, chain, amount)


def test_clamps_holds_the_bounds():
    assert clamps(0) == 1
    assert clamps(-5) == 1
    assert clamps(MAX_K + 10) == MAX_K


def test_economic_k_rises_with_risk():
    cheap = risk_table({"base": 1e-7})
    dear = risk_table({"base": 1e-3})
    low = economic_k("base", 100.0, cheap["loss"]["base"], PARAMS)
    high = economic_k("base", 100.0, dear["loss"]["base"], PARAMS)
    assert low < high


def test_economic_k_rises_with_ticket_size():
    risk = risk_table({"base": 2e-4})
    small = economic_k("base", 20.0, risk["loss"]["base"], PARAMS)
    large = economic_k("base", 50_000.0, risk["loss"]["base"], PARAMS)
    assert large > small


def test_economic_k_credits_at_once_when_risk_is_zero():
    risk = risk_table({"base": 0.0})
    assert economic_k("base", 100.0, risk["loss"]["base"], PARAMS) == 1


def test_economic_k_respects_a_flat_high_risk_ceiling():
    risk = risk_table({"base": 1.0})
    assert economic_k("base", 1.0, risk["loss"]["base"], PARAMS) == MAX_K


def test_delay_cost_scales_with_blocks_and_ticket():
    assert delay_cost_usd(1, "base", 100.0, PARAMS) == 0.0
    assert delay_cost_usd(2, "base", 100.0, PARAMS) > 0
    assert delay_cost_usd(2, "ethereum", 100.0, PARAMS) > delay_cost_usd(
        2, "base", 100.0, PARAMS
    )
    assert delay_cost_usd(12, "base", 100_000.0, PARAMS) > delay_cost_usd(
        12, "base", 100.0, PARAMS
    )


def test_calibrated_reads_the_table_per_chain():
    mixed = {
        "loss": {
            "base": [1e-2] * MAX_K,
            "polygon": [0.0] * MAX_K,
            "ethereum": [1e-6] * MAX_K,
        },
        "false_credit": {name: [0.0] * MAX_K for name in CHAINS},
    }
    deep = POLICIES["calibrated"](make("base", 100), mixed, PARAMS)
    shallow = POLICIES["calibrated"](make("polygon", 100), mixed, PARAMS)
    assert deep > shallow


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_policy_names_are_callable(name):
    assert callable(POLICIES[name])
