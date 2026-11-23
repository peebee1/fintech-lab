"""Exemption policies. A policy is a decision function plus the ceiling it claims.

`decide` owns the low value counters for its own replay: an exemption increments
them, a challenge clears them. Nothing here reads a clock or a global.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .book import Txn
from .rules import LOW_VALUE_CAP_CENTS, down_one, highest_etv, low_value_allows

LOW_VALUE = "low_value"
TRA = "tra"
CHALLENGE = "challenge"


@dataclass
class State:
    """Per replay state: the article 16 counters and why they refused."""

    cards: dict[str, tuple[int, int]] = field(default_factory=dict)
    low_value_exemptions: int = 0
    counter_refusals: int = 0
    cap_refusals: int = 0


@dataclass(frozen=True)
class Decision:
    exempt: bool
    basis: str


def _low_value(txn: Txn, state: State) -> Decision:
    if txn.amount_cents > LOW_VALUE_CAP_CENTS:
        state.cap_refusals += 1
        state.cards[txn.card] = (0, 0)
        return Decision(False, CHALLENGE)
    consecutive, cumulative = state.cards.get(txn.card, (0, 0))
    if low_value_allows(txn.amount_cents, consecutive, cumulative):
        state.cards[txn.card] = (consecutive + 1, cumulative + txn.amount_cents)
        state.low_value_exemptions += 1
        return Decision(True, LOW_VALUE)
    state.counter_refusals += 1
    state.cards[txn.card] = (0, 0)
    return Decision(False, CHALLENGE)


class Policy:
    name = "policy"
    cutoff: float = 0.0
    margin: float = 1.0
    always_etv: int = 0
    uses_tra: bool = False
    step_down: int = 0

    def etv_for(self, estimate_bps: float | None) -> int:
        if self.always_etv:
            return self.always_etv
        if not self.uses_tra:
            return 0
        if self.margin != 1.0:
            estimate_bps = None if estimate_bps is None else estimate_bps * self.margin
        etv = highest_etv(estimate_bps)
        for _ in range(self.step_down):
            etv = down_one(etv)
        return etv

    def decide(self, txn: Txn, etv: int, state: State) -> Decision:
        raise NotImplementedError


class ChallengeAll(Policy):
    """Baseline: every transaction is authenticated. The rule is satisfied by doing nothing."""

    name = "challenge_all"

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        return Decision(False, CHALLENGE)


class LowValueOnly(Policy):
    """Use the article 16 counters and nothing else. No fraud rate precondition applies."""

    name = "low_value_only"

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        return _low_value(txn, state)


class FlatTop(Policy):
    """The brochure reading: the ceiling is EUR 500, so exempt up to EUR 500."""

    name = "flat_etv_500"
    always_etv = 50000
    cutoff = 1.0

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        if txn.amount_cents <= self.always_etv:
            return Decision(True, TRA)
        return _low_value(txn, state)


class ExemptEverything(Policy):
    """No challenge at all. The unconstrained floor, and the reason the rule exists."""

    name = "exempt_everything"
    always_etv = 50000

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        return Decision(True, TRA)


class TraPlain(Policy):
    """Exempt up to the ceiling the lagged fraud rate unlocks, with no risk test."""

    name = "tra_no_risk_test"
    uses_tra = True

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        if etv > 0 and txn.amount_cents <= etv:
            return Decision(True, TRA)
        return _low_value(txn, state)


class TraRisk(Policy):
    """Same ceiling, but each transaction must also sit under a risk cutoff."""

    name = "tra_risk_cutoff"
    uses_tra = True
    cutoff = 0.18

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        if etv > 0 and txn.amount_cents <= etv and txn.risk <= self.cutoff:
            return Decision(True, TRA)
        return _low_value(txn, state)


class TraTight(Policy):
    """Ceiling one rung below what a 1.5x inflated rate unlocks, tighter risk cutoff."""

    name = "tra_tight"
    uses_tra = True
    cutoff = 0.12
    margin = 1.5
    step_down = 1

    def decide(self, txn: Txn, etv: int, state) -> Decision:
        if etv > 0 and txn.amount_cents <= etv and txn.risk <= self.cutoff:
            return Decision(True, TRA)
        return _low_value(txn, state)


def all_policies() -> tuple[Policy, ...]:
    return (
        ChallengeAll(),
        LowValueOnly(),
        TraTight(),
        TraRisk(),
        TraPlain(),
        FlatTop(),
        ExemptEverything(),
    )

