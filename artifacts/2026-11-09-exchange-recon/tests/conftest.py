import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from orderrecon import sim  # noqa: E402


@pytest.fixture(scope="session")
def dirty():
    return sim.build(seed=11, n_orders=400, per_class=6)


@pytest.fixture(scope="session")
def clean():
    return sim.build(seed=5, n_orders=150, per_class=0)
