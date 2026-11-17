"""Consent refresh policy for account to account subscriptions.

An A2A payment rides on an authorisation that expires. Refresh too early and you
spend the customer's patience on prompts you did not need. Refresh too late and the
debit is refused. The timing of the prompt decides both.

Synthetic book: 1,200 payers, 12 merchants, 360 days. No real account, institution,
or customer appears here.
"""

from consent.book import HORIZON_DAYS, LIFETIME_DAYS, Payer, build_book
from consent.policy import AdaptiveLead, FixedCadence, JustInTime, NeverRefresh, OnFailure
from consent.sim import run

__all__ = [
    "HORIZON_DAYS",
    "LIFETIME_DAYS",
    "Payer",
    "build_book",
    "AdaptiveLead",
    "FixedCadence",
    "JustInTime",
    "NeverRefresh",
    "OnFailure",
    "run",
]
