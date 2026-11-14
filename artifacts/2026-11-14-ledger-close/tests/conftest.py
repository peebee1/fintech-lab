import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from ledgerclose import book as bookmod  # noqa: E402
from ledgerclose.ledger import Ledger  # noqa: E402

FIXED = datetime(2026, 5, 20, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    return lambda: FIXED


@pytest.fixture
def ledger(tmp_path, clock):
    return Ledger(tmp_path / "journal", clock=clock)


@pytest.fixture(scope="session")
def small_book():
    return bookmod.build(seed=11, months=2, per_month=5)
