"""Integer minor units. No floats anywhere on the money path."""

from __future__ import annotations


def fmt(minor: int) -> str:
    """Render minor units as dollars, using integer division only."""
    sign = "-" if minor < 0 else ""
    value = abs(int(minor))
    return f"{sign}${value // 100:,}.{value % 100:02d}"


def parse(text: str) -> int:
    """Parse a dollar string into minor units, refusing more precision than a cent."""
    body = text.strip().lstrip("$")
    negative = body.startswith("-")
    if negative:
        body = body[1:]
    if body.count(".") > 1:
        raise ValueError(f"not an amount: {text!r}")
    whole, _, frac = body.partition(".")
    if len(frac) > 2:
        raise ValueError(f"more precision than a cent: {text!r}")
    frac = (frac + "00")[:2]
    if not whole:
        whole = "0"
    try:
        minor = int(whole) * 100 + int(frac)
    except ValueError as exc:
        raise ValueError(f"not an amount: {text!r}") from exc
    return -minor if negative else minor
