"""Exact money: integer minor units with an explicit currency exponent.

No float appears on any money path in this package. A float that is asked to hold
0.10 does not hold 0.10, and an allocation built on floats loses value one unit at a
time until somebody reconciles a payout run and finds it short.

Currencies are ISO 4217 codes with their published minor unit exponent. JPY has no
minor unit at all (exponent 0) and KWD has three, so any engine that assumes "cents"
is wrong for two thirds of the world's payment rails.
"""

from __future__ import annotations

from dataclasses import dataclass

ISO_EXPONENTS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "KWD": 3,
}


class MoneyError(ValueError):
    """A value that cannot be represented exactly in the requested currency."""


def exponent(currency: str) -> int:
    try:
        return ISO_EXPONENTS[currency]
    except KeyError:
        raise MoneyError(f"unknown currency: {currency}") from None


def scale(currency: str) -> int:
    """Minor units in one major unit: 100 for USD, 1 for JPY, 1000 for KWD."""
    return 10 ** exponent(currency)


@dataclass(frozen=True, slots=True, order=True)
class Money:
    currency: str
    minor: int

    def __post_init__(self) -> None:
        exponent(self.currency)
        if isinstance(self.minor, bool) or not isinstance(self.minor, int):
            raise MoneyError("minor units must be an int, never a float")

    def _same(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise MoneyError(f"cannot combine {self.currency} with {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.currency, self.minor + other.minor)

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.currency, self.minor - other.minor)

    def __neg__(self) -> "Money":
        return Money(self.currency, -self.minor)

    def format(self) -> str:
        """Render with exactly the currency's exponent digits, signed correctly."""
        digits = exponent(self.currency)
        sign = "-" if self.minor < 0 else ""
        whole, frac = divmod(abs(self.minor), 10 ** digits)
        if digits == 0:
            return f"{sign}{whole} {self.currency}"
        return f"{sign}{whole}.{frac:0{digits}d} {self.currency}"

    def __str__(self) -> str:
        return self.format()

    @classmethod
    def parse(cls, text: str) -> "Money":
        """Parse "<amount> <CCY>". More decimals than the currency allows is an error.

        Silently rounding here is how a per-unit price becomes a rounding question in
        the wrong place: the caller believed the amount was exact.
        """
        parts = text.split()
        if len(parts) != 2:
            raise MoneyError(f"expected '<amount> <CCY>', got {text!r}")
        return cls.from_text(parts[0], parts[1])

    @classmethod
    def from_text(cls, amount: str, currency: str) -> "Money":
        digits = exponent(currency)
        raw = amount.strip()
        sign = 1
        if raw.startswith("-"):
            sign, raw = -1, raw[1:]
        elif raw.startswith("+"):
            raw = raw[1:]
        if not raw or raw.count(".") > 1:
            raise MoneyError(f"not a decimal amount: {amount!r}")
        whole, _, frac = raw.partition(".")
        if (whole and not whole.isdigit()) or (frac and not frac.isdigit()) or not (whole or frac):
            raise MoneyError(f"not a decimal amount: {amount!r}")
        if len(frac) > digits:
            raise MoneyError(
                f"{currency} has {digits} minor digits, {amount!r} has {len(frac)}"
            )
        frac = frac.ljust(digits, "0")
        minor = int(whole or "0") * 10 ** digits + int(frac or "0")
        return cls(currency, sign * minor)
