"""Integer minor unit money helpers.

Every amount in this artifact is an integer in the currency's minor unit. No
floats touch money, so no rounding drift can appear in a total.
"""

from __future__ import annotations

CURRENCY_SYMBOL = {"EUR": "EUR ", "INR": "INR "}


def format_minor(amount: int, currency: str = "EUR") -> str:
    """Render minor units as a plain currency string, e.g. 149900 -> 'INR 1499.00'."""
    sign = "-" if amount < 0 else ""
    whole, minor = divmod(abs(amount), 100)
    return f"{sign}{CURRENCY_SYMBOL.get(currency, currency + ' ')}{whole:,}.{minor:02d}"


def bps(part: int, whole: int) -> int:
    """Part as basis points of whole. Returns 0 when whole is 0."""
    if whole == 0:
        return 0
    return round(part * 10_000 / whole)
