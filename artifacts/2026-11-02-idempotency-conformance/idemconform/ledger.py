"""Charge ledger.

The design decision the whole artifact rests on: every charge carries the
idempotency key that created it. The ledger, not the key store, is the source of
truth. A process that dies between the charge and the stored response can be
resolved by reading the ledger, because the effect and the key became one write.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class HandlerError(RuntimeError):
    """The downstream processor refused or failed the charge."""


@dataclass(frozen=True)
class Entry:
    seq: int
    account: str
    idem_key: str
    charge_id: str
    amount: int
    currency: str
    customer: str

    def as_body(self) -> dict:
        return {
            "charge_id": self.charge_id,
            "account": self.account,
            "amount": self.amount,
            "currency": self.currency,
            "customer": self.customer,
        }


class Ledger:
    """Append only list of charges, in integer minor units.

    With a path it persists every append, so a second process reads the same
    entries. That is what makes recovery a read rather than a guess.
    """

    def __init__(self, path=None) -> None:
        self.path = Path(path) if path is not None else None
        self._entries: list[Entry] = []
        self._fail_next = False
        if self.path is not None and self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [Entry(**item) for item in raw]

    def _flush(self) -> None:
        if self.path is None:
            return
        payload = [asdict(entry) for entry in self._entries]
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    @property
    def entries(self) -> list[Entry]:
        return list(self._entries)

    def fail_next_append(self) -> None:
        """Injection point: the next charge call fails at the processor."""
        self._fail_next = True

    def append(self, account: str, idem_key: str, amount: int, currency: str, customer: str) -> Entry:
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise ValueError("amount must be integer minor units")
        if amount <= 0:
            raise ValueError("amount must be positive")
        if not currency:
            raise ValueError("currency is required")
        if self._fail_next:
            self._fail_next = False
            raise HandlerError("processor returned 503")
        entry = Entry(
            seq=len(self._entries) + 1,
            account=account,
            idem_key=idem_key,
            charge_id=f"ch_{len(self._entries) + 1:04d}",
            amount=amount,
            currency=currency,
            customer=customer,
        )
        self._entries.append(entry)
        self._flush()
        return entry

    def find(self, account: str | None, idem_key: str) -> Entry | None:
        """First charge written for this key. account=None searches every account."""
        for entry in self._entries:
            if entry.idem_key != idem_key:
                continue
            if account is not None and entry.account != account:
                continue
            return entry
        return None

    def charges_for(self, account: str, idem_key: str) -> int:
        return sum(1 for e in self._entries if e.account == account and e.idem_key == idem_key)

    def total(self) -> int:
        return sum(e.amount for e in self._entries)

    def ids(self) -> set[str]:
        return {e.charge_id for e in self._entries}
