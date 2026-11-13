"""Read a predictions file from any model, including a prompt.

The contract is two columns: `loan_id,pd`. Anything can write it: a scorecard, a
gradient booster, or an LLM prompt wrapped in a loop. The harness does not care
where the probability came from, which is the point: a model that cannot produce
this file cannot be evaluated, and a model that produces it badly is visible.

Parsing is strict because silent misalignment is the classic failure: a row with a
stray space before a quoted field, or a duplicate id, shifts every label after it
and the score looks plausible.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .book import Loan

HEADER = ("loan_id", "pd")


def read_predictions(path: Path | str) -> list[tuple[int, float]]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, skipinitialspace=True)
        try:
            header = tuple(cell.strip() for cell in next(reader))
        except StopIteration:
            raise ValueError("empty predictions file") from None
        if header != HEADER:
            raise ValueError(f"header must be {','.join(HEADER)}, got {','.join(header)}")

        rows: list[tuple[int, float]] = []
        seen: set[int] = set()
        for lineno, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != len(HEADER):
                raise ValueError(f"line {lineno}: expected {len(HEADER)} fields, got {len(row)}")
            loan_id = int(row[0])
            pd = float(row[1])
            if not 0.0 <= pd <= 1.0:
                raise ValueError(f"line {lineno}: pd {pd} outside [0, 1]")
            if loan_id in seen:
                raise ValueError(f"line {lineno}: duplicate loan_id {loan_id}")
            seen.add(loan_id)
            rows.append((loan_id, pd))
    if not rows:
        raise ValueError("no prediction rows")
    return rows


def align(pairs: list[tuple[int, float]], loans: list[Loan]) -> list[float]:
    """Return one probability per loan, refusing partial coverage."""
    by_id = dict(pairs)
    missing = [loan.loan_id for loan in loans if loan.loan_id not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} loans have no prediction, first {missing[0]}")
    return [by_id[loan.loan_id] for loan in loans]
