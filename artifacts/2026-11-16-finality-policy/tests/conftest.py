import json
import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    return ARTIFACT


@pytest.fixture(scope="session")
def committed() -> dict:
    return json.loads((ARTIFACT / "results" / "summary.json").read_text())
