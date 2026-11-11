"""A deterministic synthetic dispute book. No real cardholder, no real transaction.

Every case is generated from one seed, and the generator records whether a
defence existed so every policy is scored against the same ceiling. The one
thing a policy cannot observe is whether an issuer pushback will hold.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from datetime import date, timedelta

from . import rules
from .model import Book, Case, Network, ReasonCode

START = date(2026, 1, 5)

REASON_WEIGHTS: tuple[tuple[ReasonCode, float], ...] = (
    (ReasonCode.FRAUD_CARD_ABSENT, 0.22),
    (ReasonCode.FRAUD_CARD_PRESENT, 0.12),
    (ReasonCode.NOT_RECEIVED, 0.28),
    (ReasonCode.NOT_AS_DESCRIBED, 0.18),
    (ReasonCode.DUPLICATE_PROCESSING, 0.12),
    (ReasonCode.CREDIT_NOT_PROCESSED, 0.08),
)

# log normal mean of the amount in cents, per reason code. Fraud tickets carry
# more value than a missed credit, which is why triage on count misleads.
AMOUNT_MU = {
    ReasonCode.FRAUD_CARD_ABSENT: 10.20,
    ReasonCode.FRAUD_CARD_PRESENT: 9.80,
    ReasonCode.NOT_RECEIVED: 9.00,
    ReasonCode.NOT_AS_DESCRIBED: 9.40,
    ReasonCode.DUPLICATE_PROCESSING: 9.10,
    ReasonCode.CREDIT_NOT_PROCESSED: 8.70,
}

# evidence item -> (chance the merchant holds it at all, days until it lands)
AVAILABILITY: dict[str, tuple[float, int]] = {
    "threeds_result": (0.99, 0),
    "emv_terminal_record": (0.99, 0),
    "authorization_record": (0.98, 1),
    "refund_record": (0.90, 2),
    "delivery_tracking": (0.85, 5),
    "delivery_signature": (0.70, 32),
    "terms_acceptance": (0.80, 3),
    "customer_communication": (0.65, 26),
}

PUSHBACK_RATE = 0.25
PUSHBACK_WIN_RATE = 0.55


def _pick_reason(rng: random.Random) -> ReasonCode:
    draw = rng.random()
    cumulative = 0.0
    for reason, weight in REASON_WEIGHTS:
        cumulative += weight
        if draw <= cumulative:
            return reason
    return REASON_WEIGHTS[-1][0]


def build(seed: int = 11, n: int = 2000, horizon: int = 360) -> Book:
    rng = random.Random(seed)
    cases: list[Case] = []
    for index in range(n):
        network = Network.VISA if rng.random() < 0.60 else Network.MASTERCARD
        reason = _pick_reason(rng)
        amount = int(min(900_000, max(2_000, math.exp(rng.gauss(AMOUNT_MU[reason], 0.65)))))
        txn_date = START + timedelta(days=rng.randint(0, 96))
        filed_lag = rng.randint(8, 136)
        arrival = txn_date + timedelta(days=filed_lag)

        facts: dict[str, bool] = {}
        if reason is ReasonCode.FRAUD_CARD_ABSENT:
            facts["threeds"] = rng.random() < 0.62
        elif reason is ReasonCode.FRAUD_CARD_PRESENT:
            facts["emv"] = rng.random() < 0.71

        required = rules.required_evidence(reason, facts)
        available: dict[str, date] = {}
        for item in required:
            chance, max_lag = AVAILABILITY[item]
            if rng.random() <= chance:
                available[item] = arrival + timedelta(days=rng.randint(0, max_lag))

        drafts = Case(
            id=f"cb-{index:05d}",
            network=network,
            reason=reason,
            amount_minor=amount,
            txn_date=txn_date,
            arrival=arrival,
            filed_lag=filed_lag,
            facts=facts,
            required=required,
            available=available,
            pre_arb=reason.pushes_back and rng.random() < PUSHBACK_RATE,
            pre_arb_wins=rng.random() < PUSHBACK_WIN_RATE,
            defensible=False,
        )
        cases.append(replace(drafts, defensible=rules.is_defensible(drafts)))
    return Book(cases=cases, start=START, horizon=horizon)
