import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from corrfee.bench import build
from corrfee.book import generate


@pytest.fixture(scope="session")
def book():
    return generate()


@pytest.fixture(scope="session")
def summary():
    return build()
