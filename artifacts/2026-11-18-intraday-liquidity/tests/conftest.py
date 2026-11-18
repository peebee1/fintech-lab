import json
import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from liquidity.book import BookParams, build_book  # noqa: E402

SEED = 20261118


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    return ARTIFACT


@pytest.fixture(scope="session")
def committed() -> dict:
    return json.loads((ARTIFACT / "results" / "summary.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def book():
    return build_book(SEED)


@pytest.fixture(scope="session")
def short_book():
    return build_book(SEED, BookParams(days=200))
