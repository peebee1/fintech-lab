"""Rates are quotes, not floats, and the order of conversion and splitting is a decision."""

from decimal import Decimal
from fractions import Fraction

import pytest

from fxalloc import fx
from fxalloc.money import Money, MoneyError


def test_rate_parses_exactly():
    assert fx.parse_rate("0.9231") == Fraction(9231, 10_000)
    assert fx.parse_rate("163.87") == Fraction(16387, 100)
    assert fx.parse_rate("163.87") == Fraction(Decimal("163.87"))


def test_rate_refuses_floats_and_junk():
    with pytest.raises(fx.FxError):
        fx.parse_rate(1.0842)  # type: ignore[arg-type]
    for text in ("", "abc", "-1.0", "0", "NaN", "Infinity", "1,0842"):
        with pytest.raises(fx.FxError):
            fx.parse_rate(text)


def test_conversion_across_minor_unit_exponents():
    """100.00 EUR to three destinations, each with a different number of digits."""
    usd = fx.parse_rate("1.0842")
    jpy = fx.parse_rate("163.87")
    kwd = fx.parse_rate("0.33371")
    assert fx.convert_minor(10_000, "EUR", "USD", usd) == 10_842
    assert fx.convert_minor(10_000, "EUR", "JPY", jpy) == 16_387
    assert fx.convert_minor(10_000, "EUR", "KWD", kwd) == 33_371


def test_tie_rules_are_explicit():
    half = Fraction(1, 2)
    assert fx.rounding.apply(half, "half_up") == 1
    assert fx.rounding.apply(half, "half_even") == 0
    assert fx.rounding.apply(Fraction(3, 2), "half_even") == 2
    assert fx.rounding.apply(Fraction(-1, 2), "half_up") == -1
    assert fx.rounding.apply(Fraction(-1, 2), "truncate") == 0


def test_convert_then_split_balances_in_the_target_currency():
    rate = fx.parse_rate("1.0842")
    weights = (1, 2, 3)
    total = 12_345
    converted, parts = fx.convert_then_split(total, weights, "EUR", "USD", rate)
    assert sum(parts) == converted
    assert converted == fx.convert_minor(total, "EUR", "USD", rate)


def test_split_then_convert_drifts_from_the_converted_pool():
    """The claim: same inputs, two defensible orders, two different settlements.

    0.06 EUR split three ways is 0.02 each. Converted separately that is 2 cents a
    leg, so 6. Converted once, the pool is 6.5052 cents and rounds to 7.
    """
    rate = fx.parse_rate("1.0842")
    total, weights = 6, (1, 1, 1)
    converted, _ = fx.convert_then_split(total, weights, "EUR", "USD", rate)
    legs = fx.split_then_convert(total, weights, "EUR", "USD", rate)
    assert converted == 7
    assert legs == [2, 2, 2]
    assert sum(legs) - converted == -1
    assert fx.drift(total, weights, "EUR", "USD", rate) == -1


def test_drift_is_common_not_a_corner_case():
    """Presence check across small totals, so the bench percentage is not a fluke."""
    rate = fx.parse_rate("163.87")
    drifting = sum(
        1 for total in range(1, 201) if fx.drift(total, (1, 1, 1), "EUR", "JPY", rate)
    )
    assert drifting > 100


def test_drift_is_zero_when_the_rate_is_one_and_the_currency_matches():
    rate = fx.parse_rate("1.0")
    assert fx.drift(10_000, (1, 1, 1), "USD", "USD", rate) == 0


def test_refund_conversion_is_sign_symmetric():
    rate = fx.parse_rate("1.0842")
    assert fx.convert_minor(-10_000, "EUR", "USD", rate) == -10_842
    assert fx.convert_minor(10_000, "EUR", "USD", rate) == 10_842


def test_convert_returns_money_in_the_target_currency():
    rate = fx.parse_rate("0.33371")
    converted = fx.convert(Money("EUR", 10_000), "KWD", rate)
    assert converted == Money("KWD", 33_371)
    assert converted.format() == "33.371 KWD"


def test_conversion_rejects_bad_amounts():
    rate = fx.parse_rate("1.0842")
    with pytest.raises(fx.FxError):
        fx.convert_minor(10.0, "EUR", "USD", rate)  # type: ignore[arg-type]
    with pytest.raises(fx.FxError):
        fx.convert_minor(10, "EUR", "USD", Fraction(0))
    with pytest.raises(MoneyError):
        fx.convert_minor(10, "EUR", "XYZ", rate)
