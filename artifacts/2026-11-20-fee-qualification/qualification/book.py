"""A synthetic transaction book for one merchant over a fixed number of days.

Every gap the audit later prices is drawn here, from a probability that depends on
the channel and the card product. No wall clock, no network, no unseeded random.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

from .card import L3_THRESHOLD_CENTS, PRODUCTS, RULE_INDEX, RULES, RULE_CODES

CHANNELS: tuple[str, ...] = ("card_present", "ecommerce", "recurring")
CHANNEL_WEIGHTS: tuple[tuple[str, float], ...] = (("card_present", 0.52), ("ecommerce", 0.34), ("recurring", 0.14))
PRODUCT_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("consumer_credit", 0.48),
    ("consumer_debit", 0.29),
    ("commercial_credit", 0.16),
    ("prepaid", 0.07),
)

# Median ticket by channel, in cents.
MEDIAN_TICKET: dict[str, int] = {"card_present": 6_800, "ecommerce": 9_200, "recurring": 2_900}

# Probability that a field is MISSING, by channel.
GAP_RATES: dict[str, dict[str, float]] = {
    "card_present": {
        "unauthorized": 0.05,
        "avs": 0.06,
        "cvv": 0.06,
        "stored_credential": 0.10,
        "late_batch": 0.15,
        "mcc_mismatch": 0.04,
    },
    "ecommerce": {
        "unauthorized": 0.03,
        "avs": 0.28,
        "cvv": 0.24,
        "stored_credential": 0.12,
        "late_batch": 0.15,
        "mcc_mismatch": 0.04,
    },
    "recurring": {
        "unauthorized": 0.02,
        "avs": 0.20,
        "cvv": 0.18,
        "stored_credential": 0.45,
        "late_batch": 0.12,
        "mcc_mismatch": 0.03,
    },
}

# Commercial cards arrive without their data more often than consumer cards do.
COMMERCIAL_LEVEL2_MISSING = 0.55
COMMERCIAL_LEVEL3_MISSING = 0.52
COMMERCIAL_LARGE_SHARE = 0.03

WEEKDAY_FACTOR: tuple[float, ...] = (1.00, 0.98, 1.02, 1.05, 1.18, 1.22, 0.82)


@dataclass(frozen=True)
class Transaction:
    id: int
    day: int
    amount_cents: int
    product: str
    channel: str
    authorized: bool
    avs_ok: bool
    cvv_ok: bool
    level2: bool
    level3: bool
    stored_credential: bool
    mcc_matched: bool
    same_day_batch: bool

    @property
    def commercial(self) -> bool:
        return PRODUCTS[self.product].commercial


@dataclass(frozen=True)
class Book:
    seed: int
    days: int
    transactions: tuple[Transaction, ...]

    def processed_cents(self) -> int:
        return sum(t.amount_cents for t in self.transactions)

    def by_channel(self) -> dict[str, int]:
        out = {c: 0 for c in CHANNELS}
        for t in self.transactions:
            out[t.channel] += 1
        return out

    def by_product(self) -> dict[str, int]:
        out = {p: 0 for p in PRODUCTS}
        for t in self.transactions:
            out[t.product] += 1
        return out


def failures(tx: Transaction) -> tuple[str, ...]:
    """Every rule this transaction fails, ordered by the rate card's precedence."""
    codes: list[str] = []
    if not tx.authorized:
        codes.append("unauthorized")
    if tx.commercial and not tx.level2:
        codes.append("commercial_data")
    if not tx.mcc_matched:
        codes.append("mcc_mismatch")
    if tx.channel != "card_present" and not (tx.avs_ok and tx.cvv_ok):
        codes.append("avs_cvv")
    if tx.commercial and tx.amount_cents >= L3_THRESHOLD_CENTS and not tx.level3:
        codes.append("commercial_l3")
    if tx.channel == "recurring" and not tx.stored_credential:
        codes.append("stored_credential")
    if not tx.same_day_batch:
        codes.append("late_batch")
    return tuple(codes)


def binding_tier(tx: Transaction, fixed: frozenset[str] = frozenset()) -> str | None:
    """The tier that survives after the named fixes are applied."""
    for code in failures(tx):
        if code not in fixed:
            return code
    return None


def _pick(rng: Random, pairs: tuple[tuple[str, float], ...]) -> str:
    draw = rng.random()
    total = 0.0
    for value, weight in pairs:
        total += weight
        if draw < total:
            return value
    return pairs[-1][0]


def _amount(rng: Random, channel: str, product: str) -> int:
    cents = int(math.exp(rng.gauss(math.log(MEDIAN_TICKET[channel]), 0.60)))
    if PRODUCTS[product].commercial:
        cents *= 3
        if rng.random() < COMMERCIAL_LARGE_SHARE:
            cents = rng.randint(L3_THRESHOLD_CENTS, 2_500_000)
    return max(500, min(2_500_000, cents))


def generate_book(seed: int = 20261120, days: int = 45, per_day: int = 1330, gap_scale: float = 1.0) -> Book:
    """Build the book. gap_scale scales every missing field probability, so 0.4 is
    a well integrated merchant and 1.0 is a messy one. Volume and draw order do not
    change with the scale, only which fields come back empty."""
    rng = Random(seed)
    transactions: list[Transaction] = []
    ident = 0
    for day in range(days):
        count = int(per_day * WEEKDAY_FACTOR[day % 7])
        for _ in range(count):
            channel = _pick(rng, CHANNEL_WEIGHTS)
            product = _pick(rng, PRODUCT_WEIGHTS)
            cents = _amount(rng, channel, product)
            gaps = GAP_RATES[channel]
            # Draw order is fixed so a seed reproduces the book exactly.
            authorized = rng.random() >= min(1.0, gaps["unauthorized"] * gap_scale)
            avs_ok = rng.random() >= min(1.0, gaps["avs"] * gap_scale)
            cvv_ok = rng.random() >= min(1.0, gaps["cvv"] * gap_scale)
            level2 = True
            level3 = True
            if PRODUCTS[product].commercial:
                level2 = rng.random() >= min(1.0, COMMERCIAL_LEVEL2_MISSING * gap_scale)
                if cents >= L3_THRESHOLD_CENTS:
                    level3 = rng.random() >= min(1.0, COMMERCIAL_LEVEL3_MISSING * gap_scale)
            stored_credential = rng.random() >= min(1.0, gaps["stored_credential"] * gap_scale)
            mcc_matched = rng.random() >= min(1.0, gaps["mcc_mismatch"] * gap_scale)
            same_day_batch = rng.random() >= min(1.0, gaps["late_batch"] * gap_scale)
            transactions.append(
                Transaction(
                    id=ident,
                    day=day,
                    amount_cents=cents,
                    product=product,
                    channel=channel,
                    authorized=authorized,
                    avs_ok=avs_ok,
                    cvv_ok=cvv_ok,
                    level2=level2,
                    level3=level3,
                    stored_credential=stored_credential,
                    mcc_matched=mcc_matched,
                    same_day_batch=same_day_batch,
                )
            )
            ident += 1
    return Book(seed=seed, days=days, transactions=tuple(transactions))


def code_order_is_precedence(book: Book) -> bool:
    """Every transaction's failure tuple follows the rate card order."""
    for tx in book.transactions:
        codes = failures(tx)
        if tuple(sorted(codes, key=RULE_INDEX.__getitem__)) != codes:
            return False
    return True
