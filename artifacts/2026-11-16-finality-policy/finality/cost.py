"""What waiting costs, in dollars.

Two terms per hour, per payment. The carrying term is the cost of capital on the
ticket. The fixed term is everything that does not scale with the ticket: support,
abandonment at checkout, and a merchant who cannot see the money yet. The fixed term
is what makes the right confirmation depth depend on the ticket size.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chain import CHAINS


@dataclass(frozen=True)
class Params:
    carry_per_hour: float = 1.4e-5   # 12 percent a year on the ticket
    fixed_per_hour: float = 0.25     # support and abandonment, per payment


def delay_cost_usd(k: int, chain_name: str, amount_usd: float, params: Params) -> float:
    hours = (k - 1) * CHAINS[chain_name].block_time_s / 3600.0
    return hours * (params.carry_per_hour * amount_usd + params.fixed_per_hour)
