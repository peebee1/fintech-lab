import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from routelab import data  # noqa: E402


@pytest.fixture(scope="session")
def book():
    return data.build(n=2000, seed=7)
