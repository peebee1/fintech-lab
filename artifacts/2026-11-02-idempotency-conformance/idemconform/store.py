"""Idempotency key records.

Two stores: memory, and a JSON file that survives the process. Records are copied
in and out so a caller cannot mutate stored state by holding a reference, which is
the kind of bug that makes a conformance run pass for the wrong reason.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

ABSENT = "absent"
IN_FLIGHT = "in_flight"
COMMITTED = "committed"


@dataclass
class Record:
    account: str
    key: str
    fingerprint: str
    state: str
    created_at: int
    lease_until: int = 0
    owner: str = ""
    response: dict | None = None

    def copy(self) -> "Record":
        return Record(**copy.deepcopy(asdict(self)))


class MemoryStore:
    """Key store that lives in the process. `scoped` decides whether the key is
    namespaced by account, which is the difference between two tenants sharing a
    key and nothing happening."""

    def __init__(self, scoped: bool = True) -> None:
        self.scoped = scoped
        self._records: dict[tuple[str, str], Record] = {}

    def _slot(self, account: str, key: str) -> tuple[str, str]:
        return (account, key) if self.scoped else ("*", key)

    def get(self, account: str, key: str) -> Record | None:
        record = self._records.get(self._slot(account, key))
        return record.copy() if record else None

    def put(self, record: Record) -> None:
        self._records[self._slot(record.account, record.key)] = record.copy()

    def delete(self, account: str, key: str) -> None:
        self._records.pop(self._slot(account, key), None)

    def reopen(self) -> "MemoryStore":
        """The store survived, the process did not."""
        return self


class JsonFileStore(MemoryStore):
    """Same interface, persisted after every write. Not atomic across processes:
    a real implementation needs a unique constraint in the database, which is the
    first line of the Limits section."""

    def __init__(self, path: Path | str, scoped: bool = True) -> None:
        super().__init__(scoped=scoped)
        self.path = Path(path)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("scoped", True) != self.scoped:
            raise ValueError("store file was written with a different scoping rule")
        for item in raw.get("records", []):
            record = Record(**item)
            self._records[self._slot(record.account, record.key)] = record

    def _flush(self) -> None:
        payload = {
            "scoped": self.scoped,
            "records": [asdict(r) for r in self._records.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def put(self, record: Record) -> None:
        super().put(record)
        self._flush()

    def delete(self, account: str, key: str) -> None:
        super().delete(account, key)
        self._flush()

    def reopen(self) -> "JsonFileStore":
        return JsonFileStore(self.path, scoped=self.scoped)
