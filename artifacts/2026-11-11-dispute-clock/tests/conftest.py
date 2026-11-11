import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from disputeclock import sim  # noqa: E402


@pytest.fixture(scope="session")
def book():
    return sim.build(seed=7, n=300)
