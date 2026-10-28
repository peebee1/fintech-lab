"""Split one amount across parties without losing or inventing a minor unit.

Four methods, and the difference between them is the whole point:

- ``largest_remainder``: floor every exact share, then hand the leftover units to the
  largest fractional remainders. Hamilton's method, used by every allocation problem
  from seat apportionment to fee splits. Preserves the total by construction.
- ``floor_to_largest``: floor every share and give the whole leftover to the largest
  party. What a great deal of payroll and revenue share code actually does, because it
  is a two line loop, and it silently overpays the biggest party by up to (n - 1) units.
- ``naive_half_up``: round each share independently and ship it. No correction, so the
  parts do not add back to the total.
- ``naive_half_even``: the same with banker's rounding. Less biased, still not balanced.

Sign handling: a negative total (a refund, a clawback) allocates the magnitude and
restores the sign, so the invariant holds for reversals too.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

from . import rounding


class AllocationError(ValueError):
    """The input cannot be allocated: no parties, no weight, or a non-integer amount."""


def _validate(total: int, weights: Sequence[int]) -> None:
    if isinstance(total, bool) or not isinstance(total, int):
        raise AllocationError("total must be an int number of minor units")
    if isinstance(weights, (str, bytes)) or not hasattr(weights, "__len__"):
        raise AllocationError("weights must be a sequence of ints")
    if len(weights) == 0:
        raise AllocationError("at least one party is required")
    for weight in weights:
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise AllocationError("weights must be ints")
        if weight < 0:
            raise AllocationError("weights cannot be negative")
    if sum(weights) <= 0:
        raise AllocationError("weights must sum to more than zero")


def exact_shares(total: int, weights: Sequence[int]) -> tuple[Fraction, ...]:
    """The mathematically exact share per party. Ground truth for every method below."""
    _validate(total, weights)
    denominator = sum(weights)
    return tuple(Fraction(total * weight, denominator) for weight in weights)


def _largest_remainder_nonneg(total: int, weights: Sequence[int]) -> list[int]:
    shares = exact_shares(total, weights)
    parts = [math.floor(share) for share in shares]
    leftover = total - sum(parts)
    order = sorted(
        range(len(shares)),
        key=lambda index: (-(shares[index] - parts[index]), index),
    )
    for index in order[:leftover]:
        parts[index] += 1
    return parts


def largest_remainder(total: int, weights: Sequence[int]) -> list[int]:
    sign = -1 if total < 0 else 1
    return [sign * part for part in _largest_remainder_nonneg(abs(total), weights)]


def _floor_to_largest_nonneg(total: int, weights: Sequence[int]) -> list[int]:
    _validate(total, weights)
    parts = [math.floor(share) for share in exact_shares(total, weights)]
    leftover = total - sum(parts)
    if leftover:
        winner = max(range(len(weights)), key=lambda index: (weights[index], -index))
        parts[winner] += leftover
    return parts


def floor_to_largest(total: int, weights: Sequence[int]) -> list[int]:
    sign = -1 if total < 0 else 1
    return [sign * part for part in _floor_to_largest_nonneg(abs(total), weights)]


def _independent(total: int, weights: Sequence[int], rule: Callable[[Fraction], int]) -> list[int]:
    _validate(total, weights)
    return [rule(share) for share in exact_shares(total, weights)]


def naive_half_up(total: int, weights: Sequence[int]) -> list[int]:
    return _independent(total, weights, rounding.half_up)


def naive_half_even(total: int, weights: Sequence[int]) -> list[int]:
    return _independent(total, weights, rounding.half_even)


METHODS: dict[str, Callable[[int, Sequence[int]], list[int]]] = {
    "largest_remainder": largest_remainder,
    "floor_to_largest": floor_to_largest,
    "naive_half_up": naive_half_up,
    "naive_half_even": naive_half_even,
}


def allocate(total: int, weights: Sequence[int], method: str = "largest_remainder") -> list[int]:
    try:
        rule = METHODS[method]
    except KeyError:
        raise AllocationError(f"unknown method: {method}") from None
    return rule(total, weights)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """Residual computed one way, and the same gap computed from exact shares.

    Two independently derived values. Asserting they are equal catches a sign
    convention flip that a bare ``residual == 0`` check would pass on clean data.
    """

    total: int
    allocated: int
    explained: Fraction

    @property
    def residual(self) -> int:
        return self.total - self.allocated

    @property
    def balanced(self) -> bool:
        return self.residual == 0 and self.explained == 0

    @property
    def overpaid(self) -> bool:
        return self.residual < 0


def reconcile(total: int, weights: Sequence[int], parts: Sequence[int]) -> Reconciliation:
    if len(parts) != len(weights):
        raise AllocationError("parts and weights must line up one to one")
    exact = exact_shares(total, weights)
    explained = sum((share - Fraction(part) for share, part in zip(exact, parts)), Fraction(0))
    return Reconciliation(total=total, allocated=sum(parts), explained=explained)
