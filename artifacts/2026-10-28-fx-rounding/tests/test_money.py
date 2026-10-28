"""Money is an integer plus an exponent. Parsing never rounds, adding never mixes."""

import pytest

from fxalloc.money import ISO_EXPONENTS, Money, MoneyError, exponent, scale


def test_currency_exponents_follow_iso_4217():
    assert exponent("USD") == 2
    assert exponent("EUR") == 2
    assert exponent("JPY") == 0
    assert exponent("KWD") == 3
    assert scale("USD") == 100
    assert scale("JPY") == 1
    assert scale("KWD") == 1000


def test_unknown_currency_is_refused():
    with pytest.raises(MoneyError):
        exponent("XYZ")
    with pytest.raises(MoneyError):
        Money("XYZ", 100)


def test_parse_and_format_roundtrip():
    assert Money.parse("12.34 USD") == Money("USD", 1234)
    assert Money.parse("-0.05 USD") == Money("USD", -5)
    assert Money.parse("163 JPY") == Money("JPY", 163)
    assert Money.parse("12.345 KWD") == Money("KWD", 12345)
    assert Money("USD", 1234).format() == "12.34 USD"
    assert Money("USD", -5).format() == "-0.05 USD"
    assert Money("JPY", 163).format() == "163 JPY"
    assert Money("KWD", 12345).format() == "12.345 KWD"


def test_parse_refuses_more_precision_than_the_currency_has():
    """Rounding silently at parse time hides the decision from the caller."""
    with pytest.raises(MoneyError):
        Money.parse("1.234 USD")
    with pytest.raises(MoneyError):
        Money.parse("1.5 JPY")
    with pytest.raises(MoneyError):
        Money.parse("1.2345 KWD")


def test_parse_refuses_junk():
    for text in ("12.34", "USD", "12,34 USD", "12.3.4 USD", "  ", "1.2.3 USD", "+-3 USD"):
        with pytest.raises(MoneyError):
            Money.parse(text)


def test_minor_units_must_be_ints():
    with pytest.raises(MoneyError):
        Money("USD", 12.5)  # type: ignore[arg-type]
    with pytest.raises(MoneyError):
        Money("USD", True)  # type: ignore[arg-type]


def test_arithmetic_stays_inside_one_currency():
    assert Money("USD", 1000) + Money("USD", 234) == Money("USD", 1234)
    assert Money("USD", 1000) - Money("USD", 234) == Money("USD", 766)
    assert -Money("USD", 5) == Money("USD", -5)
    with pytest.raises(MoneyError):
        Money("USD", 1000) + Money("EUR", 1)


def test_every_declared_currency_formats_with_its_own_digits():
    for code, digits in ISO_EXPONENTS.items():
        amount = 10 ** digits + 1
        rendered = Money(code, amount).format()
        assert rendered.endswith(f" {code}")
        if digits:
            assert len(rendered.split()[0].split(".")[1]) == digits
