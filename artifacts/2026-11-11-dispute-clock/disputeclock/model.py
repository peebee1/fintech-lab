"""Domain model for card chargeback representment.

Synthetic throughout: no real cardholder, no real transaction, no acquirer feed.
The windows are illustrative variants shaped like public network dispute rules.

Three clocks run on every dispute:

1. the issuer's filing window, counted from the transaction date
2. the merchant's response window, counted from the chargeback receipt date,
   and shorter for fraud reason codes than for service reason codes
3. the pre-arbitration window, counted from the day the issuer pushes back,
   which only starts once the merchant has already won

A tracker that models one of these is wrong in a way that costs money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Network(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"


class ReasonCode(str, Enum):
    FRAUD_CARD_ABSENT = "fraud_card_absent"
    FRAUD_CARD_PRESENT = "fraud_card_present"
    NOT_RECEIVED = "not_received"
    NOT_AS_DESCRIBED = "not_as_described"
    DUPLICATE_PROCESSING = "duplicate_processing"
    CREDIT_NOT_PROCESSED = "credit_not_processed"

    @property
    def is_fraud(self) -> bool:
        return self in {ReasonCode.FRAUD_CARD_ABSENT, ReasonCode.FRAUD_CARD_PRESENT}

    @property
    def pushes_back(self) -> bool:
        """Reason codes where an issuer pushback after a merchant win is common."""
        return self in {ReasonCode.NOT_AS_DESCRIBED, ReasonCode.DUPLICATE_PROCESSING}


class State(str, Enum):
    OPEN = "open"
    AUTO_WON = "auto_won"
    SUBMITTED = "submitted"
    WON = "won"
    LOST = "lost"
    FORFEITED = "forfeited"
    ACCEPTED = "accepted"
    PRE_ARB_DUE = "pre_arb_due"
    PRE_ARB_LOST = "pre_arb_lost"


TERMINAL = frozenset(
    {State.AUTO_WON, State.WON, State.LOST, State.FORFEITED, State.ACCEPTED, State.PRE_ARB_LOST}
)

# Every legal transition. The engine raises on anything else, and the suite
# replays every case to prove no illegal edge was taken.
ALLOWED: dict[State, frozenset[State]] = {
    State.OPEN: frozenset({State.AUTO_WON, State.SUBMITTED, State.FORFEITED, State.ACCEPTED}),
    State.SUBMITTED: frozenset({State.WON, State.LOST}),
    State.WON: frozenset({State.PRE_ARB_DUE}),
    State.PRE_ARB_DUE: frozenset({State.WON, State.PRE_ARB_LOST}),
}

WON_STATES = frozenset({State.AUTO_WON, State.WON})


def liability_shifted(reason: ReasonCode, facts: dict[str, bool]) -> bool:
    """True when the merchant holds a liability defence that needs no evidence.

    An authenticated 3DS transaction moves card-absent fraud liability to the
    issuer. A chip read at a chip capable terminal does the same for card-present.
    """
    if reason is ReasonCode.FRAUD_CARD_ABSENT:
        return bool(facts.get("threeds"))
    if reason is ReasonCode.FRAUD_CARD_PRESENT:
        return bool(facts.get("emv"))
    return False


@dataclass(frozen=True)
class Case:
    id: str
    network: Network
    reason: ReasonCode
    amount_minor: int
    txn_date: date
    arrival: date
    filed_lag: int
    facts: dict[str, bool]
    required: tuple[str, ...]
    available: dict[str, date]
    pre_arb: bool
    pre_arb_wins: bool
    defensible: bool

    @property
    def procedural_invalid(self) -> bool:
        """The issuer filed outside its own window, so the merchant wins on procedure."""
        return self.filed_lag > FILING_DAYS[self.network]

    @property
    def liability_shifted(self) -> bool:
        return liability_shifted(self.reason, self.facts)

    @property
    def free_win(self) -> bool:
        """A case that needs zero evidence to win."""
        return self.procedural_invalid or self.liability_shifted


FILING_DAYS = {Network.VISA: 120, Network.MASTERCARD: 120}


@dataclass
class Book:
    cases: list[Case] = field(default_factory=list)
    start: date = date(2026, 1, 5)
    horizon: int = 210

    @property
    def by_arrival(self) -> dict[date, list[Case]]:
        out: dict[date, list[Case]] = {}
        for case in self.cases:
            out.setdefault(case.arrival, []).append(case)
        return out

    @property
    def total_minor(self) -> int:
        return sum(case.amount_minor for case in self.cases)

    @property
    def recoverable_minor(self) -> int:
        return sum(case.amount_minor for case in self.cases if case.defensible)
