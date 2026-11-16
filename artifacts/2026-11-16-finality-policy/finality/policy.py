"""Confirmation policies. Each one answers: how many blocks before we credit?

The interesting part is what the answer is allowed to depend on. A fixed count
depends on nothing. The tiered rule depends on the ticket. The chain defaults depend
on the chain. The calibrated rule depends on a measured per chain loss curve and on
what waiting costs, and it is the only one that uses both.
"""

from __future__ import annotations

import math
from typing import Callable

from .chain import CHAINS
from .cost import Params, delay_cost_usd

MAX_K = 64

# A latency target per ticket band, in seconds. This is the rule a team writes when
# it wants the checkout to feel the same everywhere, and it is why a fast chain ends
# up with fewer blocks of protection than a slow one.
TIER_TARGETS: tuple[tuple[float, float], ...] = (
    (100.0, 12.0),
    (1_000.0, 45.0),
    (10_000.0, 120.0),
    (math.inf, 300.0),
)


def clamps(value: int) -> int:
    return max(1, min(MAX_K, value))


def seconds_to_blocks(seconds: float, chain_name: str) -> int:
    return max(1, math.ceil(seconds / CHAINS[chain_name].block_time_s))


def economic_k(
    chain_name: str,
    amount_usd: float,
    loss_risk: list[float],
    params: Params,
    max_k: int = MAX_K,
) -> int:
    """Smallest k whose expected loss is no worse than the cost of waiting for it."""
    for k in range(1, max_k + 1):
        expected_loss = amount_usd * loss_risk[k - 1]
        if expected_loss <= delay_cost_usd(k, chain_name, amount_usd, params):
            return k
    return max_k


def credit_on_inclusion(payment, risk, params) -> int:
    return 1


def fixed_12(payment, risk, params) -> int:
    return 12


CHAIN_DEFAULTS = {"base": 12, "polygon": 30, "ethereum": 32}


def chain_defaults(payment, risk, params) -> int:
    return CHAIN_DEFAULTS[payment.chain]


def ticket_tiers(payment, risk, params) -> int:
    for cap, target_s in TIER_TARGETS:
        if payment.amount_usd <= cap:
            return clamps(seconds_to_blocks(target_s, payment.chain))
    return MAX_K


def calibrated(payment, risk, params) -> int:
    return clamps(
        economic_k(
            payment.chain,
            payment.amount_usd,
            risk["loss"][payment.chain],
            params,
        )
    )


PolicyFn = Callable[[object, dict, Params], int]

POLICIES: dict[str, PolicyFn] = {
    "credit_on_inclusion": credit_on_inclusion,
    "fixed_12": fixed_12,
    "chain_defaults": chain_defaults,
    "ticket_tiers": ticket_tiers,
    "calibrated": calibrated,
}


def confirmations(name: str, payment, risk: dict, params: Params) -> int:
    return POLICIES[name](payment, risk, params)
