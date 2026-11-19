"""Synthetic authorisation book.

All data is synthetic and labelled as such. Amounts are integer cents. Days are
integers from an arbitrary epoch, never wall clock.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

SYNTHETIC = True

# kind, share of book, mean ticket in cents, log normal sigma
KINDS = (
    ("restaurant", 0.34, 7200, 0.45),
    ("retail", 0.30, 12800, 0.60),
    ("split", 0.16, 21000, 0.50),
    ("hotel", 0.10, 56000, 0.50),
    ("late", 0.10, 9600, 0.55),
)

# share of authorisations that never settle: abandoned carts, no shows, cancelled orders
NEVER_CAPTURE = {
    "restaurant": 0.06,
    "retail": 0.10,
    "split": 0.04,
    "hotel": 0.08,
    "late": 0.12,
}

ARRIVAL_DAYS = 170
LAST_CAPTURE_DAY = 25
MAX_EXPIRY_DAYS = 28
HORIZON = ARRIVAL_DAYS + LAST_CAPTURE_DAY + MAX_EXPIRY_DAYS + 10


@dataclass(frozen=True)
class Capture:
    """A settlement request against an authorisation, in cents, on a day."""

    day: int
    cents: int


@dataclass(frozen=True)
class Auth:
    auth_id: int
    subject: str
    kind: str
    authorized_cents: int
    approved_day: int
    captures: tuple[Capture, ...]

    @property
    def requested_cents(self) -> int:
        return sum(c.cents for c in self.captures)

    @property
    def expiry_day(self) -> int:
        return self.approved_day + MAX_EXPIRY_DAYS


@dataclass(frozen=True)
class Book:
    auths: tuple[Auth, ...]
    horizon: int

    @property
    def authorized_cents(self) -> int:
        return sum(a.authorized_cents for a in self.auths)

    @property
    def requested_cents(self) -> int:
        return sum(a.requested_cents for a in self.auths)

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.auths:
            out[a.kind] = out.get(a.kind, 0) + 1
        return out


def _log_normal(rng: random.Random, mean_cents: int, sigma: float) -> int:
    mu = math.log(mean_cents) - sigma * sigma / 2
    return max(100, int(round(rng.lognormvariate(mu, sigma))))


def _split_cents(total: int, parts: int, rng: random.Random) -> list[int]:
    """Split cents exactly: integer parts that sum to total."""
    weights = [rng.uniform(0.6, 1.4) for _ in range(parts)]
    scale = total / sum(weights)
    chunks = [int(w * scale) for w in weights]
    chunks[-1] += total - sum(chunks)
    return chunks


def _captures_for(kind: str, amount: int, approved_day: int, rng: random.Random) -> tuple[Capture, ...]:
    if kind == "restaurant":
        tip = round(amount * rng.uniform(0.08, 0.26))
        return (Capture(approved_day + rng.choice((1, 1, 1, 2, 2, 3)), amount + tip),)

    if kind == "retail":
        return (Capture(approved_day + rng.choice((0, 0, 1, 1, 2, 3)), amount),)

    if kind == "split":
        parts = rng.choice((2, 2, 3, 3, 4))
        days = sorted(rng.sample(range(1, 13), parts))
        chunks = _split_cents(amount, parts, rng)
        return tuple(Capture(approved_day + d, c) for d, c in zip(days, chunks))

    if kind == "hotel":
        stay = amount
        consumed = round(stay * rng.uniform(0.85, 1.0))
        return (Capture(approved_day + rng.randint(3, 14), consumed),)

    if kind == "late":
        return (Capture(approved_day + rng.randint(8, LAST_CAPTURE_DAY), amount),)

    raise ValueError(f"unknown kind {kind}")


def generate_book(seed: int = 20261119, count: int = 2500) -> Book:
    """Build one deterministic synthetic book."""
    rng = random.Random(seed)

    # Draw the whole book before numbering it, so ids carry no information.
    drafts: list[tuple[str, int, int, tuple[Capture, ...]]] = []
    cumulative = []
    acc = 0.0
    for _, share, _, _ in KINDS:
        acc += share
        cumulative.append(acc)

    for _ in range(count):
        roll = rng.random()
        kind, mean_cents, sigma = KINDS[-1][0], KINDS[-1][2], KINDS[-1][3]
        for index, (name, _, m, s) in enumerate(KINDS):
            if roll <= cumulative[index]:
                kind, mean_cents, sigma = name, m, s
                break

        approved_day = rng.randint(0, ARRIVAL_DAYS)
        if kind == "hotel":
            stay = _log_normal(rng, mean_cents, sigma)
            amount = round(stay * 1.15)
        else:
            stay = _log_normal(rng, mean_cents, sigma)
            amount = stay

        if rng.random() < NEVER_CAPTURE[kind]:
            drafts.append((kind, amount, approved_day, ()))
            continue

        drafts.append((kind, amount, approved_day, _captures_for(kind, stay, approved_day, rng)))

    rng.shuffle(drafts)
    auths = tuple(
        Auth(
            auth_id=index + 1,
            subject=f"card-{index + 1:05d}",
            kind=kind,
            authorized_cents=amount,
            approved_day=approved_day,
            captures=captures,
        )
        for index, (kind, amount, approved_day, captures) in enumerate(drafts)
    )
    return Book(auths=auths, horizon=HORIZON)
