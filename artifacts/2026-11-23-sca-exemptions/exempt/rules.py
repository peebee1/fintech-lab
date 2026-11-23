"""SCA exemption selection: rules that decide what may skip a challenge.

Pure functions and integer money everywhere. No clock, no network.
"""

from __future__ import annotations

# Money is integer cents of EUR.
EURO = 100

# Article 16 style low value exemption.
LOW_VALUE_CAP_CENTS = 30 * EURO
LOW_VALUE_CONSECUTIVE = 5
LOW_VALUE_CUMULATIVE_CENTS = 100 * EURO

# Exemption threshold values and the reference fraud rate that unlocks each one,
# in basis points of value. Ordered from the most generous band down.
# Remote electronic card based payments, EU 2018/389 Annex.
REFERENCE_BPS = (
    (500 * EURO, 1.0),
    (250 * EURO, 6.0),
    (100 * EURO, 13.0),
)


def reference_bps(etv_cents: int) -> float | None:
    """Reference fraud rate for an exemption threshold value, or None if no TRA applies."""
    for etv, ref in REFERENCE_BPS:
        if etv_cents == etv:
            return ref
    return None


def highest_etv(fraud_bps: float | None) -> int:
    """Largest exemption threshold the given overall fraud rate unlocks.

    Zero means no transaction risk analysis exemption is available and every
    transaction above the low value cap must be challenged. The rate is compared
    against the whole instrument population, not against a band, which is the part
    most internal dashboards get wrong.
    """
    if fraud_bps is None:
        return 0
    for etv, ref in REFERENCE_BPS:
        if fraud_bps <= ref:
            return etv
    return 0


def low_value_allows(amount_cents: int, consecutive: int, cumulative_cents: int) -> bool:
    """Whether the next transaction fits inside the low value counters."""
    if amount_cents > LOW_VALUE_CAP_CENTS:
        return False
    if consecutive >= LOW_VALUE_CONSECUTIVE:
        return False
    return cumulative_cents + amount_cents <= LOW_VALUE_CUMULATIVE_CENTS


def bps(part_cents: int, whole_cents: int) -> float:
    """Basis points of value, with a zero guard."""
    if whole_cents <= 0:
        return 0.0
    return part_cents * 10000.0 / whole_cents


_LADDER = (500 * EURO, 250 * EURO, 100 * EURO, 0)


def down_one(etv_cents: int) -> int:
    """The next lower exemption threshold, for a policy that wants headroom."""
    if etv_cents not in _LADDER:
        return 0
    return _LADDER[min(_LADDER.index(etv_cents) + 1, len(_LADDER) - 1)]
