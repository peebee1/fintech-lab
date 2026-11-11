"""Network variants, evidence requirements, and the three deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import netcalendar
from .model import Case, Network, ReasonCode

# Analyst minutes to assemble each evidence item. Machine records are free
# because they are already in the payment stack; everything else costs a person.
EVIDENCE_MINUTES: dict[str, int] = {
    "threeds_result": 0,
    "emv_terminal_record": 0,
    "authorization_record": 1,
    "refund_record": 2,
    "delivery_tracking": 4,
    "delivery_signature": 6,
    "terms_acceptance": 8,
    "customer_communication": 12,
}

PRE_ARB_MINUTES = 10


@dataclass(frozen=True)
class Variant:
    filing_days: int
    response_days: int
    response_days_fraud: int
    pre_arb_days: int


VARIANTS: dict[Network, Variant] = {
    Network.VISA: Variant(filing_days=120, response_days=30, response_days_fraud=20, pre_arb_days=30),
    Network.MASTERCARD: Variant(
        filing_days=120, response_days=45, response_days_fraud=20, pre_arb_days=45
    ),
}


def variant(case: Case) -> Variant:
    return VARIANTS[case.network]


def response_window(case: Case) -> int:
    """Fraud reason codes get a shorter window than service reason codes."""
    v = variant(case)
    return v.response_days_fraud if case.reason.is_fraud else v.response_days


def response_deadline(case: Case) -> date:
    return netcalendar.add_window(case.arrival, response_window(case))


def pre_arb_deadline(pushback_day: date, case: Case) -> date:
    return netcalendar.add_window(pushback_day, variant(case).pre_arb_days)


def required_evidence(reason: ReasonCode, facts: dict[str, bool]) -> tuple[str, ...]:
    """The evidence set that constitutes a defence, given the terminal facts.

    A tuple, not a score: a partial set is not a weaker defence, it is no defence.
    """
    if reason is ReasonCode.FRAUD_CARD_ABSENT:
        if facts.get("threeds"):
            return ("threeds_result",)
        return ("authorization_record", "customer_communication")
    if reason is ReasonCode.FRAUD_CARD_PRESENT:
        if facts.get("emv"):
            return ("emv_terminal_record",)
        return ("authorization_record", "customer_communication")
    if reason is ReasonCode.NOT_RECEIVED:
        return ("delivery_signature",)
    if reason is ReasonCode.NOT_AS_DESCRIBED:
        return ("terms_acceptance", "customer_communication")
    if reason is ReasonCode.DUPLICATE_PROCESSING:
        return ("authorization_record", "terms_acceptance")
    if reason is ReasonCode.CREDIT_NOT_PROCESSED:
        return ("refund_record",)
    raise ValueError(f"unhandled reason code: {reason}")


def evidence_minutes(items: tuple[str, ...]) -> int:
    return sum(EVIDENCE_MINUTES[item] for item in items)


def available_on(case: Case, day: date) -> tuple[str, ...]:
    return tuple(sorted(item for item, landed in case.available.items() if landed <= day))


def is_defensible(case: Case) -> bool:
    """Could any policy have won this case, given what the merchant holds?"""
    if case.procedural_invalid or case.liability_shifted:
        return True
    deadline = response_deadline(case)
    return all(case.available.get(item, date.max) <= deadline for item in case.required)


def payment_received(day: date) -> date:
    """Pushback arrives 20 days after the merchant's win."""
    return day + timedelta(days=20)
