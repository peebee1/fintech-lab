"""Cross currency conversion in minor units, with the order of operations made visible.

The bug this module exists to name: a payout whose total is converted once and then
split lands on a different number than the same payout split and then converted leg by
leg. Both are defensible in isolation, they disagree by a few minor units, and the
difference shows up as an unreconciled settlement line rather than as an exception.

Rates are exact rationals parsed from decimal strings. A rate is a quote, not a float:
"163.87" is 16387/100, and treating it as binary floating point puts noise into the
answer before the first rounding decision is made.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Callable, Sequence

from . import rounding
from .alloc import METHODS, largest_remainder
from .money import Money, exponent


class FxError(ValueError):
    """A rate or currency pair that cannot be converted."""


def parse_rate(text: str) -> Fraction:
    """Exact rational from a decimal quote. Rejects anything the vendor would not send."""
    if not isinstance(text, str):
        raise FxError("rate must be a decimal string, not a float")
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise FxError(f"not a decimal rate: {text!r}") from None
    if not value.is_finite() or value <= 0:
        raise FxError(f"rate must be finite and positive: {text!r}")
    return Fraction(value)


def convert_minor(
    amount_minor: int,
    source: str,
    target: str,
    rate: Fraction,
    mode: str = "half_up",
) -> int:
    """Convert an amount between currencies with different minor unit exponents."""
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise FxError("amount must be an int number of minor units")
    if rate <= 0:
        raise FxError("rate must be positive")
    exact = Fraction(amount_minor) * rate * Fraction(10) ** (exponent(target) - exponent(source))
    return rounding.apply(exact, mode)


def convert_minor_float(amount_minor: int, source: str, target: str, rate_text: str) -> int:
    """The float64 path, kept only so the divergence can be counted.

    Python's round() is half to even, so this is the closest fair comparison to the
    exact path with the same tie rule.
    """
    value = float(amount_minor) * float(rate_text) * (10.0 ** (exponent(target) - exponent(source)))
    return int(round(value))


def convert(money: Money, target: str, rate: Fraction, mode: str = "half_up") -> Money:
    return Money(target, convert_minor(money.minor, money.currency, target, rate, mode))


def convert_then_split(
    total_minor: int,
    weights: Sequence[int],
    source: str,
    target: str,
    rate: Fraction,
    method: str = "largest_remainder",
    mode: str = "half_up",
) -> tuple[int, list[int]]:
    """Convert the pool once, then allocate in the settlement currency."""
    converted = convert_minor(total_minor, source, target, rate, mode)
    return converted, METHODS[method](converted, weights)


def split_then_convert(
    total_minor: int,
    weights: Sequence[int],
    source: str,
    target: str,
    rate: Fraction,
    method: str = "largest_remainder",
    mode: str = "half_up",
) -> list[int]:
    """Allocate in the source currency, then convert each leg. The legacy order."""
    parts = METHODS[method](total_minor, weights)
    return [convert_minor(part, source, target, rate, mode) for part in parts]


def drift(
    total_minor: int,
    weights: Sequence[int],
    source: str,
    target: str,
    rate: Fraction,
    method: str = "largest_remainder",
    mode: str = "half_up",
    rule: Callable[[int, Sequence[int]], list[int]] = largest_remainder,
) -> int:
    """Sum of converted legs minus the converted pool total, in target minor units."""
    converted, _ = convert_then_split(total_minor, weights, source, target, rate, method, mode)
    legs = split_then_convert(total_minor, weights, source, target, rate, method, mode)
    return sum(legs) - converted
