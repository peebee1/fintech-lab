"""Simulate a policy over a book and a reorg history.

Two clocks decide the outcome for one payment:

- the credit height, inclusion_height + k - 1, when the merchant balance moves
- the detection height, the height at which the replacement branch is as long as the
  block that held the payment, when the payment is known to have been reorged out

If detection is at or below the credit height, waiting caught it: the payment is
re-included and credited later, with no loss. If detection is above it, the merchant
was credited while the chain could still take the payment back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .chain import CHAINS, Reorg
from .book import Payment
from .cost import Params, delay_cost_usd

REINCLUDE_BLOCKS = 1


@dataclass(frozen=True)
class ReorgIndex:
    """Every block height that a reorg reaches back over, to its deepest reorg."""

    by_height: dict[int, Reorg]

    def hit(self, height: int) -> Reorg | None:
        return self.by_height.get(height)


def index(reorgs: Sequence[Reorg]) -> ReorgIndex:
    by_height: dict[int, Reorg] = {}
    for reorg in reorgs:
        for height in range(reorg.fork_height, reorg.last_invalidated + 1):
            current = by_height.get(height)
            if current is None:
                by_height[height] = reorg
                continue
            gap = reorg.depth - (height - reorg.fork_height)
            old_gap = current.depth - (height - current.fork_height)
            if gap > old_gap:
                by_height[height] = reorg
    return ReorgIndex(by_height)


@dataclass(frozen=True)
class Outcome:
    pid: str
    chain: str
    amount_cents: int
    k: int
    credit_height: int
    status: str          # ok, held, reverted, lost
    delay_s: int
    exposed_cents: int   # credited before the chain could no longer take it back
    loss_cents: int


def evaluate(
    payment: Payment,
    reorg_index: ReorgIndex,
    k: int,
    drop_prob: float,
) -> Outcome:
    chain = CHAINS[payment.chain]
    block_time = chain.block_time_s
    height = payment.inclusion_height
    nominal_credit = height + k - 1
    hit = reorg_index.hit(height)
    if hit is not None and hit.chain != payment.chain:
        hit = None

    if hit is None:
        delay = nominal_credit * block_time - payment.arrival_s
        return Outcome(
            payment.pid, payment.chain, payment.amount_cents, k,
            nominal_credit, "ok", delay, 0, 0,
        )

    detection = hit.last_invalidated
    if detection <= nominal_credit:
        credit = detection + REINCLUDE_BLOCKS + k
        delay = credit * block_time - payment.arrival_s
        return Outcome(
            payment.pid, payment.chain, payment.amount_cents, k,
            credit, "held", delay, 0, 0,
        )

    delay = nominal_credit * block_time - payment.arrival_s
    dropped = payment.drop_draw < drop_prob
    return Outcome(
        payment.pid,
        payment.chain,
        payment.amount_cents,
        k,
        nominal_credit,
        "lost" if dropped else "reverted",
        delay,
        payment.amount_cents,
        payment.amount_cents if dropped else 0,
    )


def run_policy(
    book: Sequence[Payment],
    reorgs: dict[str, list[Reorg]],
    ks: dict[str, int] | int,
    drop_prob: dict[str, float] | None = None,
) -> list[Outcome]:
    """`ks` is either one k per payment id or a single fixed k for the whole book."""
    if drop_prob is None:
        drop_prob = {name: chain.drop_prob for name, chain in CHAINS.items()}
    indexes = {name: index(items) for name, items in reorgs.items()}
    out = []
    for payment in book:
        k = ks[payment.pid] if isinstance(ks, dict) else ks
        out.append(
            evaluate(payment, indexes[payment.chain], k, drop_prob[payment.chain])
        )
    return out


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest rank, stepping down. Cheap, stable, and stated in the README."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index_at = min(len(ordered) - 1, int(math.floor(q * (len(ordered) - 1))))
    return float(ordered[index_at])


BANDS: tuple[tuple[str, float], ...] = (
    ("under_100", 100.0),
    ("100_to_1000", 1_000.0),
    ("1000_to_10000", 10_000.0),
    ("over_10000", float("inf")),
)


def band_of(amount_usd: float) -> str:
    for name, cap in BANDS:
        if amount_usd <= cap:
            return name
    return BANDS[-1][0]


def metrics(outcomes: Sequence[Outcome], params: Params | None = None) -> dict:
    params = params or Params()
    n = len(outcomes)
    delays = [o.delay_s for o in outcomes]
    value_cents = sum(o.amount_cents for o in outcomes)
    lost = [o for o in outcomes if o.status == "lost"]
    reverted = [o for o in outcomes if o.status == "reverted"]
    false_credits = lost + reverted
    weighted_delay = (
        sum(o.amount_cents * o.delay_s for o in outcomes) / value_cents
        if value_cents
        else 0.0
    )
    loss_cents = sum(o.loss_cents for o in outcomes)
    wait_cost = sum(
        (o.delay_s / 3600.0)
        * (params.carry_per_hour * o.amount_cents / 100.0 + params.fixed_per_hour)
        for o in outcomes
    )
    return {
        "payments": n,
        "value_usd": round(value_cents / 100.0, 2),
        "false_credits": len(false_credits),
        "false_credit_rate": round(len(false_credits) / n, 5) if n else 0.0,
        "exposed_usd": round(sum(o.exposed_cents for o in outcomes) / 100.0, 2),
        "loss_usd": round(loss_cents / 100.0, 2),
        "loss_bps": round(10_000 * loss_cents / value_cents, 3) if value_cents else 0.0,
        "largest_loss_usd": round(max((o.loss_cents for o in lost), default=0) / 100.0, 2),
        "loss_by_band": {
            band: {
                "lost": sum(1 for o in lost if band_of(o.amount_cents / 100.0) == band),
                "loss_usd": round(
                    sum(o.loss_cents for o in lost if band_of(o.amount_cents / 100.0) == band)
                    / 100.0,
                    2,
                ),
            }
            for band, _ in BANDS
        },
        "wait_cost_usd": round(wait_cost, 2),
        "total_cost_usd": round(loss_cents / 100.0 + wait_cost, 2),
        "median_delay_s": percentile(delays, 0.5),
        "p95_delay_s": percentile(delays, 0.95),
        "value_weighted_delay_s": round(weighted_delay, 1),
        "share_credited_60s": round(
            sum(1 for d in delays if d <= 60) / n, 4
        ) if n else 0.0,
    }


def per_chain(outcomes: Sequence[Outcome]) -> dict[str, dict]:
    return {
        name: metrics([o for o in outcomes if o.chain == name]) for name in CHAINS
    }
