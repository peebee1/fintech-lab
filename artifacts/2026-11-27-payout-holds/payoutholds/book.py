"""The synthetic seller book: sales, refunds with lags, and exits.

Everything is drawn once, before any payout policy runs, so two policies see the
same orders, the same refunds and the same exits. Money is integer cents.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field

# Risk bands. The band drives order rate, refund rate and expected tenure, which is
# the only thing a marketplace can observe before it has history.
BANDS = ("established", "new", "risky")

BAND_PARAMS = {
    "established": {
        "share": 0.70,
        "daily_orders": 1.15,
        "refund_rate": 0.030,
        "mean_tenure": 420.0,
        "join_share": 0.05,
        "ticket_median_cents": 11_000,
    },
    "new": {
        "share": 0.20,
        "daily_orders": 0.70,
        "refund_rate": 0.055,
        "mean_tenure": 130.0,
        "join_share": 0.55,
        "ticket_median_cents": 8_500,
    },
    "risky": {
        "share": 0.10,
        "daily_orders": 0.95,
        "refund_rate": 0.140,
        "mean_tenure": 75.0,
        "join_share": 0.35,
        "ticket_median_cents": 9_500,
    },
}

ORDER_SIGMA = 0.65
ADMIN_FEE_CENTS = 1_500
MAX_REFUND_LAG = 120


@dataclass(frozen=True)
class Seller:
    id: str
    band: str
    join_day: int
    exit_day: int

    @property
    def active_days(self) -> int:
        return max(0, self.exit_day - self.join_day)


@dataclass(frozen=True)
class Order:
    id: int
    seller_id: str
    day: int
    amount_cents: int


@dataclass(frozen=True)
class Refund:
    order_id: int
    seller_id: str
    sale_day: int
    arrival_day: int
    amount_cents: int
    fee_cents: int

    @property
    def cost_cents(self) -> int:
        return self.amount_cents + self.fee_cents


@dataclass
class Book:
    seed: int
    days: int
    sellers: list[Seller]
    orders: list[Order]
    refunds: list[Refund]
    horizon: int = field(default=0)

    def __post_init__(self) -> None:
        last_sale = max((o.day for o in self.orders), default=0)
        last_refund = max((r.arrival_day for r in self.refunds), default=0)
        # The horizon must cover the last sale plus every downstream window, or the
        # final refunds land outside the simulation and the books do not balance.
        self.horizon = max(self.days, last_sale + 1, last_refund + 1) + 1

    @property
    def gmv_cents(self) -> int:
        return sum(o.amount_cents for o in self.orders)

    @property
    def refund_cost_cents(self) -> int:
        return sum(r.cost_cents for r in self.refunds)

    def digest(self) -> str:
        payload = {
            "sellers": [[s.id, s.band, s.join_day, s.exit_day] for s in self.sellers],
            "orders": [[o.id, o.seller_id, o.day, o.amount_cents] for o in self.orders],
            "refunds": [
                [r.order_id, r.arrival_day, r.amount_cents, r.fee_cents] for r in self.refunds
            ],
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]

    def by_seller(self) -> dict[str, list[Order]]:
        out: dict[str, list[Order]] = {s.id: [] for s in self.sellers}
        for order in self.orders:
            out[order.seller_id].append(order)
        return out

    def refunds_by_seller(self) -> dict[str, list[Refund]]:
        out: dict[str, list[Refund]] = {s.id: [] for s in self.sellers}
        for refund in self.refunds:
            out[refund.seller_id].append(refund)
        return out


def _seller_count(total: int) -> dict[str, int]:
    counts = {band: int(round(total * BAND_PARAMS[band]["share"])) for band in BANDS}
    drift = total - sum(counts.values())
    counts["established"] += drift
    return counts


def generate(seed: int = 20261127, sellers: int = 400, days: int = 180) -> Book:
    """Build the book. Same seed, same book, byte for byte."""
    rng = random.Random(seed)

    specs: list[tuple[str, int, int]] = []
    for band in BANDS:
        for _ in range(_seller_count(sellers)[band]):
            params = BAND_PARAMS[band]
            if rng.random() < params["join_share"]:
                join = rng.randrange(0, max(1, days - 10))
            else:
                join = 0
            tenure = max(14, int(rng.expovariate(1.0 / params["mean_tenure"])))
            specs.append((band, join, join + tenure))

    # Shuffle before numbering, so an id tie break cannot carry the band.
    rng.shuffle(specs)
    seller_rows = [
        Seller(id=f"s{index:04d}", band=band, join_day=join, exit_day=exit_day)
        for index, (band, join, exit_day) in enumerate(specs)
    ]
    seller_by_id = {s.id: s for s in seller_rows}

    orders: list[Order] = []
    refunds: list[Refund] = []
    next_order_id = 1
    for seller in seller_rows:
        params = BAND_PARAMS[seller.band]
        mu = math.log(params["ticket_median_cents"])
        stop = min(days, seller.exit_day)
        for day in range(seller.join_day, stop):
            count = _poisson(rng, params["daily_orders"])
            for _ in range(count):
                amount = max(500, int(rng.lognormvariate(mu, ORDER_SIGMA)))
                order = Order(id=next_order_id, seller_id=seller.id, day=day, amount_cents=amount)
                orders.append(order)
                next_order_id += 1
                if rng.random() < params["refund_rate"]:
                    refunds.append(_make_refund(rng, order))

    refunds.sort(key=lambda r: (r.arrival_day, r.order_id))
    return Book(seed=seed, days=days, sellers=seller_rows, orders=orders, refunds=refunds)


def _make_refund(rng: random.Random, order: Order) -> Refund:
    roll = rng.random()
    share = 1.0 if roll < 0.80 else round(rng.uniform(0.20, 0.90), 3)
    lag = _refund_lag(rng)
    return Refund(
        order_id=order.id,
        seller_id=order.seller_id,
        sale_day=order.day,
        arrival_day=order.day + lag,
        amount_cents=int(order.amount_cents * share),
        fee_cents=ADMIN_FEE_CENTS,
    )


def _refund_lag(rng: random.Random) -> int:
    """Refund lags are a mixture: most close quickly, a tail runs for months."""
    roll = rng.random()
    if roll < 0.65:
        return rng.randint(2, 21)
    if roll < 0.90:
        return rng.randint(21, 60)
    return rng.randint(60, MAX_REFUND_LAG)


def _poisson(rng: random.Random, lam: float) -> int:
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1
