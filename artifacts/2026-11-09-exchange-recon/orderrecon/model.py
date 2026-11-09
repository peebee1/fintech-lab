"""Types shared by the simulator, the reconcilers, and the bench."""

from __future__ import annotations

from dataclasses import dataclass, field

BUY = "BUY"
SELL = "SELL"

OPEN = "OPEN"
FILLED = "FILLED"
CANCELLED = "CANCELLED"
REJECTED = "REJECTED"

BREAK_CLASSES = (
    "duplicate_fill",
    "missing_fill",
    "price_drift",
    "qty_mismatch",
    "broker_qty_lag",
    "fill_after_cancel",
    "orphan_fill",
    "phantom_position",
)

# Classes whose evidence is a disagreement between the exchange tape and the
# app's own fill archive. These are the only ones allowed to carry a book
# correction, which keeps the explained delta test independent of positions.
FILL_LEVEL = frozenset({"duplicate_fill", "missing_fill", "price_drift", "qty_mismatch"})


def sign(side: str) -> int:
    return 1 if side == BUY else -1


@dataclass(frozen=True)
class Fill:
    """One print. Used for both the exchange tape and the app archive."""

    trade_id: str
    order_id: str
    symbol: str
    side: str
    qty: int
    price: int
    fee: int
    seq: int


def cash_flow(fill: Fill) -> int:
    """Signed cash effect in paise. Buy pays out, sell takes in, both pay the fee."""
    return -sign(fill.side) * fill.qty * fill.price - fill.fee


@dataclass(frozen=True)
class BrokerOrder:
    """What the broker's order API says at end of session."""

    order_id: str
    symbol: str
    side: str
    qty: int
    status: str
    filled_qty: int
    avg_price: int
    cancel_seq: int | None


@dataclass(frozen=True)
class Break:
    cls: str
    key: str
    shares: int = 0
    cash: int = 0
    impact: int = 0
    detail: str = ""


@dataclass
class Session:
    tape: list[Fill]
    broker: dict[str, BrokerOrder]
    app_fills: list[Fill]
    app_positions: dict[str, int]
    app_cash: int
    start_cash: int
    truth: list[dict]
    last_price: dict[str, int]
    symbols: tuple[str, ...] = field(default_factory=tuple)
