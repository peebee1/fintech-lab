"""Rounding of exact rational values onto the integer lattice.

Every rounding rule here takes a Fraction and returns an int. The sign is handled by
rounding the magnitude and restoring the sign, so a refund rounds exactly like the
charge it reverses instead of drifting toward positive infinity on ties.
"""

from __future__ import annotations

import math
from fractions import Fraction


class RoundingError(ValueError):
    """Unknown rounding mode."""


def half_up(value: Fraction) -> int:
    """Round to nearest, ties away from zero. The default in most payment APIs."""
    sign = -1 if value < 0 else 1
    magnitude = abs(value)
    return sign * math.floor(magnitude + Fraction(1, 2))


def half_even(value: Fraction) -> int:
    """Round to nearest, ties to even. Python's round(), and ISO 80000-1's default."""
    sign = -1 if value < 0 else 1
    magnitude = abs(value)
    floor = math.floor(magnitude)
    rest = magnitude - floor
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2 == 1):
        floor += 1
    return sign * floor


def truncate(value: Fraction) -> int:
    """Toward zero. What most FX desks actually quote against, and the worst for totals."""
    sign = -1 if value < 0 else 1
    return sign * math.floor(abs(value))


MODES = {"half_up": half_up, "half_even": half_even, "truncate": truncate}


def apply(value: Fraction, mode: str) -> int:
    try:
        rule = MODES[mode]
    except KeyError:
        raise RoundingError(f"unknown rounding mode: {mode}") from None
    return rule(value)
