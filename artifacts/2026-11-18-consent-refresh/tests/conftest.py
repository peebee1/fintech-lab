import json
import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from consent.book import Payer, build_book  # noqa: E402


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    return ARTIFACT


@pytest.fixture(scope="session")
def committed() -> dict:
    return json.loads((ARTIFACT / "results" / "summary.json").read_text())


@pytest.fixture(scope="session")
def small_book() -> list[Payer]:
    return build_book(seed=7, size=40)


def one_payer(**overrides) -> Payer:
    base = dict(
        pid="T0",
        merchant="test-merchant",
        bill_cents=10_000,
        due_day=5,
        consent_start=0,
        latency_median_h=1.0,
        abandon_prob=0.0,
        churn_hazard=0.0,
    )
    base.update(overrides)
    return Payer(**base)
