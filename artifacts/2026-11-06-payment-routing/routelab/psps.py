"""Three acquirers: published fee schedules, hidden approval behaviour.

The fee schedule is what a merchant sees in a contract. The approval curve is
what the merchant learns after a month of traffic, and it is the part that is
modelled per segment rather than per provider.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import data


@dataclass(frozen=True)
class Drift:
    """A mid-stream change in one provider's approval behaviour.

    Real acquirers do not send a changelog when an issuer relationship changes.
    The regime shift is the reason a learned router has a job that a rule table
    does not: the rule table keeps routing to the provider that used to win.
    """

    at: int  # transaction index where the new regime starts
    psp: str
    delta: float  # logit shift, negative means worse
    token: str  # context token the shift applies to

    def shift(self, txn: data.Txn) -> float:
        if txn.index >= self.at and self.token in txn.tokens:
            return self.delta
        return 0.0


@dataclass(frozen=True)
class Psp:
    name: str
    bps: int  # ad valorem, basis points of the captured amount
    fixed: int  # cents per captured transaction
    base_logit: float
    deltas: dict[str, float] = field(default_factory=dict)

    def fee(self, amount: int) -> int:
        return data.fee_cents(amount, self.bps, self.fixed)

    def logit(self, txn: data.Txn, shift: float = 0.0) -> float:
        return self.base_logit + shift + sum(self.deltas.get(t, 0.0) for t in txn.tokens)

    def approval(self, txn: data.Txn, shift: float = 0.0) -> float:
        return 1.0 / (1.0 + math.exp(-self.logit(txn, shift)))

    def expected_net(
        self, txn: data.Txn, margin_bps: int = data.MARGIN_BPS, drift: "Drift | None" = None
    ) -> int:
        """Expected cents from one attempt, rounded to the cent."""
        shift = drift.shift(txn) if drift and drift.psp == self.name else 0.0
        p = self.approval(txn, shift)
        gross = p * data.margin_cents(txn.amount, margin_bps)
        cost = p * self.fee(txn.amount)
        return round(gross - cost - data.OPS_CENTS)



# The cheapest headline schedule is not the cheapest at every ticket size, and
# it is weakest exactly where its price is best. That is the whole problem.
PSPS: tuple[Psp, ...] = (
    Psp(
        name="alpha",
        bps=120,
        fixed=8,
        base_logit=2.20,
        deltas={
            "channel:credit": 0.10,
            "channel:debit": -0.55,
            "region:cross_border": -0.80,
            "band:micro": -0.10,
            "band:large": -0.05,
        },
    ),
    Psp(
        name="bravo",
        bps=155,
        fixed=4,
        base_logit=2.05,
        deltas={
            "channel:credit": -0.15,
            "channel:debit": 0.40,
            "region:cross_border": -0.25,
            "band:micro": 0.05,
            "band:large": -0.10,
        },
    ),
    Psp(
        name="charlie",
        bps=185,
        fixed=0,
        base_logit=2.00,
        deltas={
            "channel:credit": -0.05,
            "channel:debit": 0.10,
            "region:cross_border": 0.60,
            "region:domestic": -0.30,
            "band:micro": -0.35,
            "band:large": 0.20,
        },
    ),
)

BY_NAME = {psp.name: psp for psp in PSPS}


def names() -> tuple[str, ...]:
    return tuple(psp.name for psp in PSPS)
