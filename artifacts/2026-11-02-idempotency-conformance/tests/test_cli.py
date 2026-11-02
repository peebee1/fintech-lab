"""Results are written by the committed code, and never by a test.

The default directory resolves inside the function so a test that redirects it
cannot silently rewrite the committed payload.
"""

import json
from pathlib import Path

from idemconform import cli


def test_write_results_lands_in_the_requested_directory(tmp_path: Path):
    payload = cli.write_results(tmp_path)
    assert (tmp_path / "conformance.json").exists()
    assert (tmp_path / "violations.json").exists()
    assert (tmp_path / "summary.md").exists()
    assert json.loads((tmp_path / "conformance.json").read_text())["meta"]["checks"] == payload["meta"]["checks"]


def test_write_results_is_byte_stable_across_two_writes(tmp_path: Path):
    first, second = tmp_path / "one", tmp_path / "two"
    cli.write_results(first)
    cli.write_results(second)
    for name in ("conformance.json", "violations.json", "summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_write_results_does_not_touch_the_committed_directory(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "elsewhere")
    cli.write_results()
    assert (tmp_path / "elsewhere" / "conformance.json").exists()
