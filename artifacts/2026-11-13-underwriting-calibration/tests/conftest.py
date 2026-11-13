import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from uwcal import book  # noqa: E402
from uwcal.models import Scorecard  # noqa: E402


@pytest.fixture(scope="session")
def loans():
    return book.build(seed=13, n=1200)


@pytest.fixture(scope="session")
def parts(loans):
    return book.split(loans)


@pytest.fixture(scope="session")
def card(parts):
    return Scorecard(l2=1.0).fit(parts["train"])
