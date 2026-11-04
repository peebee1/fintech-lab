import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from screenlab import data  # noqa: E402


@pytest.fixture(scope="session")
def dataset():
    """The committed dataset, built once: building it is the slow part."""
    return data.build()
