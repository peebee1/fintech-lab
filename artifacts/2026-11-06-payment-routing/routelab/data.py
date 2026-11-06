"""Money arithmetic and the synthetic transaction book.

All money is integer cents. Fees are rounded half up, once, at the same place
the ledger would round them, so the totals reconcile exactly instead of
"to within a cent".
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

MARGIN_BPS = 1500  # merchant gross margin on a captured sale
OPS_CENTS = 2  # cost of one authorization attempt, independent of outcome

CHANNELS = ("credit", "debit")
REGIONS = ("domestic", "cross_border")
BANDS = ("micro", "mid", "large")

# amount ranges in cents, and the share of the book each band carries
BAND_RANGE = {"micro": (300, 3000), "mid": (3001, 20000), "large": (20001, 150000)}
BAND_MIX = (("micro", 0.25), ("mid", 0.45), ("large", 0.30))
DEBIT_SHARE = 0.55
CROSS_BORDER_SHARE = 0.22


@dataclass(frozen=True)
class Txn:
    index: int
    amount: int  # cents
    channel: str
    region: str
    band: str

    @property
    def context(self) -> str:
        return f"{self.channel}/{self.region}/{self.band}"

    @property
    def tokens(self) -> tuple[str, ...]:
        return (f"channel:{self.channel}", f"region:{self.region}", f"band:{self.band}")


def fee_cents(amount: int, bps: int, fixed: int) -> int:
    """Half up rounding, integer only."""
    return (amount * bps + 5000) // 10000 + fixed


def margin_cents(amount: int, margin_bps: int = MARGIN_BPS) -> int:
    return (amount * margin_bps + 5000) // 10000


def _pick(rng: random.Random, weighted: tuple[tuple[str, float], ...]) -> str:
    draw = rng.random()
    cursor = 0.0
    for name, share in weighted:
        cursor += share
        if draw < cursor:
            return name
    return weighted[-1][0]


def build(n: int = 60000, seed: int = 20261106) -> list[Txn]:
    """Synthetic, seeded, no real cardholder anywhere.

    Amounts are drawn uniformly inside a band, which keeps the band boundaries
    honest: the oracle has to beat a fee schedule that changes slope at those
    boundaries, and a bandit sees the same coarse context the router gets.
    """
    rng = random.Random(seed)
    book: list[Txn] = []
    for index in range(n):
        band = _pick(rng, BAND_MIX)
        low, high = BAND_RANGE[band]
        amount = rng.randint(low, high)
        channel = "debit" if rng.random() < DEBIT_SHARE else "credit"
        region = "cross_border" if rng.random() < CROSS_BORDER_SHARE else "domestic"
        book.append(Txn(index=index, amount=amount, channel=channel, region=region, band=band))
    return book


def digest(book: list[Txn]) -> str:
    h = hashlib.sha256()
    for txn in book:
        h.update(f"{txn.index},{txn.amount},{txn.channel},{txn.region},{txn.band}\n".encode())
    return h.hexdigest()[:16]


def mix(book: list[Txn]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for txn in book:
        counts[txn.context] = counts.get(txn.context, 0) + 1
    return {k: round(v / len(book), 4) for k, v in sorted(counts.items())}
