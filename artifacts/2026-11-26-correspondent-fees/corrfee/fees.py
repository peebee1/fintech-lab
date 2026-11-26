"""Tariffs for the three MT103 charge codes.

The numbers are a modelled tariff, not a published one. What is real is the
shape: every fee has a floor and a cap, so a small ticket pays a rate that has
nothing to do with its basis points, and a large ticket stops paying more.

One rule matters for the whole artifact: the sender bank's own charge is the
same work under all three codes. Under SHA it is billed on top of the amount,
under BEN it is deducted from the amount, and under OUR it is inside the bundle.
That is how the code moves a cost without creating one.
"""

from __future__ import annotations

OUR_BPS = 28
OUR_MIN_CENTS = 3_500
OUR_MAX_CENTS = 25_000

BANK_BPS = 8
BANK_MIN_CENTS = 1_000
BANK_MAX_CENTS = 6_000


def priced(amount_cents: int, bps: int, minimum: int, maximum: int) -> int:
    """A bank fee: basis points of the amount, rounded up, floored, capped."""
    if amount_cents <= 0:
        return 0
    raw = -(-amount_cents * bps // 10_000)
    return max(minimum, min(maximum, raw))


def our_fee(amount_cents: int) -> int:
    """OUR: one bundled charge that already contains every intermediary's cut."""
    return priced(amount_cents, OUR_BPS, OUR_MIN_CENTS, OUR_MAX_CENTS)


def sender_bank_fee(amount_cents: int) -> int:
    """The sender bank's own charge. Billed on top under SHA, deducted under BEN."""
    return priced(amount_cents, BANK_BPS, BANK_MIN_CENTS, BANK_MAX_CENTS)


def sha_fee(amount_cents: int) -> int:
    """SHA: the sender pays its own bank only, so the chain comes off the amount."""
    return sender_bank_fee(amount_cents)
