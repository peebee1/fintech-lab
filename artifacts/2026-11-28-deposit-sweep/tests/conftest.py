"""Shared fixtures. The book and the bench are built once per session."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from depositsweep.bench import run
from depositsweep.book import generate_book


@pytest.fixture(scope="session")
def book():
    return generate_book()


@pytest.fixture(scope="session")
def summary():
    return run()
