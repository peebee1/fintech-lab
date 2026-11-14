"""Append only JSONL storage. The only write API is append, and every append hits the disk."""

from __future__ import annotations

import json
import os
from pathlib import Path


class StoreCorrupt(RuntimeError):
    """A line in the file is not a record. Fail loudly instead of skipping it."""


class JsonlStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        records: list[dict] = []
        for number, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise StoreCorrupt(f"{self.path.name} line {number}: {exc}") from exc
        return records

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(blob + "\n")
            handle.flush()
            os.fsync(handle.fileno())
