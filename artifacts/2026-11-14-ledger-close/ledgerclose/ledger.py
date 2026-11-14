"""An append only, hash chained ledger whose close either reproduces or does not.

Rules this module enforces, each raised as a named Refusal:

- Unbalanced: the postings of one entry must sum to zero.
- ClosedPeriod: no entry may land in a period that has been closed.
- NoAmend: there is no edit. A correction is a reversal plus a new entry.
- ReversalOfMissing, ReversalNotExact, AlreadyReversed, ReversalBeforeOriginal.
- OutOfOrderClose, AlreadyClosed.

Balances are never stored. They are derived from the entries on every read, so there is
no running total to drift away from the facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .entry import GENESIS, KINDS, Entry, Line, digest, from_record, normalise, recompute, seal, to_record
from .store import JsonlStore

PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def period_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def period_start(period: str) -> date:
    if not PERIOD_RE.match(period):
        raise ValueError(f"bad period: {period}")
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, 1)


def period_end(period: str) -> date:
    start = period_start(period)
    return date(start.year + (start.month == 12), start.month % 12 + 1, 1) - timedelta(days=1)


def shift_period(period: str, months: int) -> str:
    start = period_start(period)
    index = start.year * 12 + (start.month - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


class Refusal(Exception):
    """A named rule stopped the write. The name is the API."""

    def __init__(self, rule: str, detail: str = "") -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"{rule}: {detail}" if detail else rule)


@dataclass(frozen=True)
class CloseRecord:
    period: str
    closed_at: str
    entries_through_seq: int
    chain_head: str
    control_totals: dict[str, int]
    digest: str

    def record(self) -> dict:
        return {
            "period": self.period,
            "closed_at": self.closed_at,
            "entries_through_seq": self.entries_through_seq,
            "chain_head": self.chain_head,
            "control_totals": dict(sorted(self.control_totals.items())),
            "digest": self.digest,
        }

    @staticmethod
    def parse(record: dict) -> "CloseRecord":
        return CloseRecord(
            period=record["period"],
            closed_at=record["closed_at"],
            entries_through_seq=record["entries_through_seq"],
            chain_head=record["chain_head"],
            control_totals=dict(record["control_totals"]),
            digest=record["digest"],
        )


def close_digest(record: CloseRecord) -> str:
    return digest({
        "period": record.period,
        "entries_through_seq": record.entries_through_seq,
        "chain_head": record.chain_head,
        "control_totals": [[account, amount] for account, amount in sorted(record.control_totals.items())],
    })


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_seq: int | None
    reason: str


@dataclass(frozen=True)
class CloseCheck:
    ok: bool
    period: str
    reason: str
    recorded: dict[str, int]
    recomputed: dict[str, int]


@dataclass(frozen=True)
class TrialRow:
    account: str
    debit_minor: int
    credit_minor: int
    net_minor: int


@dataclass(frozen=True)
class TrialBalance:
    period: str
    rows: tuple[TrialRow, ...]
    total_debit_minor: int
    total_credit_minor: int

    @property
    def balanced(self) -> bool:
        return self.total_debit_minor == self.total_credit_minor

    @property
    def net_minor(self) -> int:
        return sum(row.net_minor for row in self.rows)


class Ledger:
    def __init__(self, directory: Path | str, clock=None) -> None:
        self.directory = Path(directory)
        self.entries = JsonlStore(self.directory / "entries.jsonl")
        self.closes_file = JsonlStore(self.directory / "closes.jsonl")
        self._clock = clock or utcnow
        self._entries: list[Entry] = [from_record(record) for record in self.entries.read()]
        self._by_id: dict[str, Entry] = {entry.entry_id: entry for entry in self._entries}
        self._by_key: dict[str, Entry] = {entry.idempotency_key: entry for entry in self._entries if entry.idempotency_key}
        self._closes: list[CloseRecord] = [CloseRecord.parse(record) for record in self.closes_file.read()]

    # -- reads -----------------------------------------------------------------

    @property
    def journal(self) -> tuple[Entry, ...]:
        return tuple(self._entries)

    @property
    def closes(self) -> tuple[CloseRecord, ...]:
        return tuple(self._closes)

    @property
    def closed_periods(self) -> frozenset[str]:
        return frozenset(record.period for record in self._closes)

    def close_record(self, period: str) -> CloseRecord | None:
        for record in self._closes:
            if record.period == period:
                return record
        return None

    def entries_in(self, period: str, through_seq: int | None = None) -> list[Entry]:
        start, end = period_start(period), period_end(period)
        return [
            entry for entry in self._entries
            if start <= entry.business_date <= end and (through_seq is None or entry.seq <= through_seq)
        ]

    def control_totals(self, period: str, through_seq: int | None = None) -> dict[str, int]:
        totals: dict[str, int] = {}
        for entry in self.entries_in(period, through_seq):
            for line in entry.lines:
                totals[line.account] = totals.get(line.account, 0) + line.amount_minor
        return {account: amount for account, amount in sorted(totals.items()) if amount != 0}

    def balances(self, as_of: date | None = None, through_seq: int | None = None) -> dict[str, int]:
        """Derived on every call. There is no stored running balance to go stale."""
        totals: dict[str, int] = {}
        for entry in self._entries:
            if as_of is not None and entry.business_date > as_of:
                continue
            if through_seq is not None and entry.seq > through_seq:
                continue
            for line in entry.lines:
                totals[line.account] = totals.get(line.account, 0) + line.amount_minor
        return {account: amount for account, amount in sorted(totals.items())}

    def trial_balance(self, period: str) -> TrialBalance:
        """Debits equal credits per period, computed in one pass and never stored."""
        rows: dict[str, TrialRow] = {}
        for entry in self.entries_in(period):
            for line in entry.lines:
                row = rows.get(line.account, TrialRow(line.account, 0, 0, 0))
                rows[line.account] = TrialRow(
                    line.account,
                    row.debit_minor + max(0, line.amount_minor),
                    row.credit_minor + max(0, -line.amount_minor),
                    row.net_minor + line.amount_minor,
                )
        ordered = tuple(sorted(rows.values(), key=lambda row: row.account))
        return TrialBalance(
            period=period,
            rows=ordered,
            total_debit_minor=sum(row.debit_minor for row in ordered),
            total_credit_minor=sum(row.credit_minor for row in ordered),
        )

    def drift(self, period: str) -> dict[str, int]:
        """Per account change between what the close reported and what the facts say now."""
        record = self.close_record(period)
        if record is None:
            return {}
        now = self.control_totals(period, through_seq=record.entries_through_seq)
        accounts = set(record.control_totals) | set(now)
        return {
            account: now.get(account, 0) - record.control_totals.get(account, 0)
            for account in sorted(accounts)
            if now.get(account, 0) != record.control_totals.get(account, 0)
        }

    # -- writes ----------------------------------------------------------------

    def open_business_date(self) -> date:
        day = self._clock().date()
        if period_of(day) not in self.closed_periods:
            return day
        probe = shift_period(max(self.closed_periods), 1)
        while probe in self.closed_periods:
            probe = shift_period(probe, 1)
        return period_start(probe)

    def post(
        self,
        lines: Iterable[Line],
        business_date: date,
        *,
        idempotency_key: str | None = None,
        kind: str = "normal",
        reverses: str | None = None,
        entry_id: str | None = None,
        posted_at: datetime | None = None,
    ) -> Entry:
        if kind not in KINDS:
            raise Refusal("UnknownKind", kind)
        postings = normalise(Line(line.account, int(line.amount_minor)) for line in lines)
        if not postings or all(line.amount_minor == 0 for line in postings):
            raise Refusal("EmptyPosting")
        if any(not line.account.strip() for line in postings):
            raise Refusal("EmptyAccount")

        if idempotency_key and idempotency_key in self._by_key:
            return self._by_key[idempotency_key]

        period = period_of(business_date)
        if period in self.closed_periods:
            sealed = self.close_record(period)
            raise Refusal("ClosedPeriod", f"{period} closed at {sealed.closed_at if sealed else 'unknown'}")

        total = sum(line.amount_minor for line in postings)
        if total != 0:
            raise Refusal("Unbalanced", f"lines sum to {total} minor units")

        if reverses is not None or kind == "reversal":
            if reverses is None:
                raise Refusal("ReversalTargetMissing")
            original = self._by_id.get(reverses)
            if original is None:
                raise Refusal("ReversalOfMissing", reverses)
            if any(entry.reverses == reverses for entry in self._entries):
                raise Refusal("AlreadyReversed", reverses)
            expected = sorted((line.account, -line.amount_minor) for line in original.lines)
            if expected != [(line.account, line.amount_minor) for line in postings]:
                raise Refusal("ReversalNotExact", f"{reverses} is not the exact inverse of this entry")
            if business_date < original.business_date:
                raise Refusal("ReversalBeforeOriginal", f"{business_date} precedes {original.business_date}")

        identifier = entry_id or f"e{len(self._entries) + 1:06d}"
        if identifier in self._by_id:
            raise Refusal("DuplicateEntryId", identifier)

        moment = posted_at or self._clock()
        moment = moment.astimezone(timezone.utc).replace(microsecond=0)
        entry = seal(
            Entry(
                entry_id=identifier,
                business_date=business_date,
                posted_at=moment,
                lines=postings,
                kind="reversal" if reverses is not None else kind,
                reverses=reverses,
                idempotency_key=idempotency_key,
            ),
            seq=len(self._entries) + 1,
            prev_hash=self._entries[-1].hash if self._entries else GENESIS,
        )
        self.entries.append(to_record(entry))
        self._entries.append(entry)
        self._by_id[identifier] = entry
        if idempotency_key:
            self._by_key[idempotency_key] = entry
        return entry

    def amend(self, entry_id: str, lines: Iterable[Line] | None = None) -> Entry:
        raise Refusal("NoAmend", f"{entry_id}: append a reversal, then post the correction in the open period")

    def reverse(self, entry_id: str, business_date: date | None = None) -> Entry:
        original = self._by_id.get(entry_id)
        if original is None:
            raise Refusal("ReversalOfMissing", entry_id)
        day = business_date or self.open_business_date()
        return self.post([line.inverted() for line in original.lines], day, reverses=entry_id)

    def close(self, period: str) -> CloseRecord:
        if not PERIOD_RE.match(period):
            raise Refusal("BadPeriod", period)
        if period in self.closed_periods:
            raise Refusal("AlreadyClosed", period)
        earlier = sorted({
            period_of(entry.business_date) for entry in self._entries
            if entry.business_date < period_start(period)
        })
        missing = [item for item in earlier if item not in self.closed_periods]
        if missing:
            raise Refusal("OutOfOrderClose", f"close {missing[0]} first")

        head = self._entries[-1] if self._entries else None
        record = CloseRecord(
            period=period,
            closed_at=self._clock().astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            entries_through_seq=head.seq if head else 0,
            chain_head=head.hash if head else GENESIS,
            control_totals=self.control_totals(period),
            digest="",
        )
        record = replace(record, digest=close_digest(record))
        self.closes_file.append(record.record())
        self._closes.append(record)
        return record

    # -- proofs ----------------------------------------------------------------

    def verify(self) -> ChainCheck:
        prev = GENESIS
        for index, entry in enumerate(self._entries, 1):
            if entry.seq != index:
                return ChainCheck(False, index - 1, entry.seq, f"seq gap: expected {index}, found {entry.seq}")
            if entry.prev_hash != prev:
                return ChainCheck(False, index - 1, entry.seq, "prev_hash does not match the entry before it")
            if recompute(entry) != entry.hash:
                return ChainCheck(False, index - 1, entry.seq, "entry contents changed after it was chained")
            prev = entry.hash
        return ChainCheck(True, len(self._entries), None, "chain intact")

    def verify_close(self, record: CloseRecord) -> CloseCheck:
        if record.entries_through_seq > len(self._entries):
            return CloseCheck(False, record.period, "journal is shorter than the close record", record.control_totals, {})
        head = self._entries[record.entries_through_seq - 1] if record.entries_through_seq else None
        head_hash = head.hash if head else GENESIS
        recomputed = self.control_totals(record.period, through_seq=record.entries_through_seq)
        if head_hash != record.chain_head:
            return CloseCheck(False, record.period, "chain head at the cut has changed", record.control_totals, recomputed)
        if recomputed != record.control_totals:
            return CloseCheck(False, record.period, "control totals no longer reproduce", record.control_totals, recomputed)
        if close_digest(record) != record.digest:
            return CloseCheck(False, record.period, "record does not match its own digest", record.control_totals, recomputed)
        return CloseCheck(True, record.period, "close reproduces", record.control_totals, recomputed)

    def verify_all_closes(self) -> list[CloseCheck]:
        return [self.verify_close(record) for record in self._closes]
