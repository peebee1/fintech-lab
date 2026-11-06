"""Outcomes with common random numbers.

Every policy sees the same transaction stream and, for a given (transaction,
provider, attempt), the same uniform draw. Comparing two policies is therefore
a paired comparison: the difference is the routing decision, not the luck of
the draw. A policy that makes more attempts consumes the same luck for the
attempts it does make.
"""

from __future__ import annotations

import hashlib

from . import psps
from .data import Txn

HARD_DECLINE_SHARE = 0.35
RETRY_SUCCESS_FACTOR = 0.55


def uniform(seed: int, txn_index: int, psp: str, attempt: int) -> float:
    key = f"{seed}|{txn_index}|{psp}|{attempt}".encode()
    raw = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(raw, "big") / 2**64


def is_hard(seed: int, txn_index: int, psp: str, attempt: int) -> bool:
    return uniform(seed + 1, txn_index, psp, attempt) < HARD_DECLINE_SHARE


def authorizes(
    seed: int,
    txn: Txn,
    psp: str,
    attempt: int,
    retry: bool,
    drift: psps.Drift | None = None,
) -> bool:
    """True when this attempt captures the sale.

    A first attempt uses the provider's own approval probability. A retry is
    cheaper to lose: the issuer has already seen the authorization once, so the
    probability is discounted. A hard decline cannot be recovered by retrying,
    which is why the bench only retries soft declines.
    """
    shift = drift.shift(txn) if drift and drift.psp == psp else 0.0
    base = psps.BY_NAME[psp].approval(txn, shift)
    p = base * RETRY_SUCCESS_FACTOR if retry else base
    return uniform(seed, txn.index, psp, attempt) < p
