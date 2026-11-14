"""An entry is a fact: it is never edited, and it carries the hash of the entry before it."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Iterable

GENESIS = "0" * 64
KINDS = ("normal", "reversal", "adjustment")


def digest(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Line:
    """A signed posting. Positive is a debit, negative is a credit."""

    account: str
    amount_minor: int

    def inverted(self) -> "Line":
        return Line(self.account, -self.amount_minor)


def normalise(lines: Iterable[Line]) -> tuple[Line, ...]:
    """Sort lines so two callers sending the same postings hash identically."""
    return tuple(sorted(lines, key=lambda line: (line.account, line.amount_minor)))


@dataclass(frozen=True)
class Entry:
    entry_id: str
    business_date: date
    posted_at: datetime
    lines: tuple[Line, ...]
    kind: str = "normal"
    reverses: str | None = None
    idempotency_key: str | None = None
    currency: str = "INR"
    seq: int = 0
    prev_hash: str = GENESIS
    hash: str = ""

    def payload(self) -> dict:
        return {
            "seq": self.seq,
            "entry_id": self.entry_id,
            "business_date": self.business_date.isoformat(),
            "posted_at": iso(self.posted_at),
            "kind": self.kind,
            "reverses": self.reverses,
            "idempotency_key": self.idempotency_key,
            "currency": self.currency,
            "lines": [[line.account, line.amount_minor] for line in self.lines],
            "prev_hash": self.prev_hash,
        }


def seal(entry: Entry, seq: int, prev_hash: str) -> Entry:
    body = replace(entry, seq=seq, prev_hash=prev_hash, hash="")
    return replace(body, hash=digest(body.payload()))


def recompute(entry: Entry) -> str:
    return digest(replace(entry, hash="").payload())


def to_record(entry: Entry) -> dict:
    return {**entry.payload(), "hash": entry.hash}


def from_record(record: dict) -> Entry:
    return Entry(
        entry_id=record["entry_id"],
        business_date=date.fromisoformat(record["business_date"]),
        posted_at=parse_iso(record["posted_at"]),
        lines=normalise(Line(account, amount) for account, amount in record["lines"]),
        kind=record["kind"],
        reverses=record["reverses"],
        idempotency_key=record["idempotency_key"],
        currency=record["currency"],
        seq=record["seq"],
        prev_hash=record["prev_hash"],
        hash=record["hash"],
    )
