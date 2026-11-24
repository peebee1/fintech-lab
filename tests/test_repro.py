"""The reproducibility gate has to fail when a number is edited, not only when it is absent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import repro  # noqa: E402

EMIT = '''\
import json
from pathlib import Path

out = Path("results")
out.mkdir(exist_ok=True)
(out / "summary.json").write_text(json.dumps({"net": 1234, "trades": 7}, indent=2) + "\\n")
(out / "timing.json").write_text(json.dumps({"modes": {"naive": 2.0, "reserve": 5.0}}, indent=2) + "\\n")
'''

ENTRY = {
    "steps": [
        {
            "argv": ["python", "emit.py"],
            "byte": ["results/summary.json"],
            "structure": ["results/timing.json"],
        }
    ]
}


def make_artifact(tmp_path: Path, name: str = "art") -> Path:
    art = tmp_path / name
    (art / "results").mkdir(parents=True)
    (art / "emit.py").write_text(EMIT, encoding="utf-8")
    (art / "results" / "summary.json").write_text(
        json.dumps({"net": 1234, "trades": 7}, indent=2) + "\n", encoding="utf-8"
    )
    (art / "results" / "timing.json").write_text(
        json.dumps({"modes": {"naive": 2.0, "reserve": 5.0}}, indent=2) + "\n", encoding="utf-8"
    )
    return art


def test_clean_artifact_reproduces(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    report = repro.reproduce(art, ENTRY)
    assert report.ok, report.failures
    assert report.compared == 2


def test_edited_number_fails(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    committed = art / "results" / "summary.json"
    committed.write_text(json.dumps({"net": 1235, "trades": 7}, indent=2) + "\n", encoding="utf-8")
    report = repro.reproduce(art, ENTRY)
    assert not report.ok
    assert "results/summary.json: committed file does not reproduce from code" in report.failures


def test_missing_key_in_timing_file_fails(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    timing = art / "results" / "timing.json"
    timing.write_text(json.dumps({"modes": {"naive": 2.0}}, indent=2) + "\n", encoding="utf-8")
    report = repro.reproduce(art, ENTRY)
    assert not report.ok
    assert any("unexpected keys in produced output: reserve" in f for f in report.failures)


def test_timing_value_drift_is_reported_not_gated(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    timing = art / "results" / "timing.json"
    timing.write_text(
        json.dumps({"modes": {"naive": 9.0, "reserve": 5.0}}, indent=2) + "\n", encoding="utf-8"
    )
    report = repro.reproduce(art, ENTRY)
    assert report.ok, report.failures
    assert any("modes.naive" in d for d in report.drift)


def test_produced_but_uncommitted_fails(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    (art / "results" / "timing.json").unlink()
    entry = {"steps": [dict(ENTRY["steps"][0], structure=[], byte=["results/timing.json"])]}
    report = repro.reproduce(art, entry)
    assert not report.ok
    assert "results/timing.json: produced but not committed" in report.failures


def test_committed_file_the_command_never_writes_fails(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    (art / "results" / "stale.json").write_text("{}\n", encoding="utf-8")
    entry = {"steps": [dict(ENTRY["steps"][0], structure=[], byte=["results/stale.json"])]}
    report = repro.reproduce(art, entry)
    assert not report.ok
    assert "results/stale.json: not produced by the command" in report.failures


def test_failing_command_is_not_a_pass(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    (art / "emit.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    report = repro.reproduce(art, ENTRY)
    assert not report.ok
    assert any("exited 3" in f for f in report.failures)


def test_reproduce_leaves_committed_files_untouched(tmp_path: Path) -> None:
    art = make_artifact(tmp_path)
    before = {p.name: p.read_bytes() for p in (art / "results").iterdir()}
    repro.reproduce(art, ENTRY)
    after = {p.name: p.read_bytes() for p in (art / "results").iterdir()}
    assert before == after


def test_every_artifact_has_a_manifest_entry() -> None:
    manifest = repro.load_manifest()
    on_disk = sorted(p.name for p in (ROOT / "artifacts").iterdir() if p.is_dir())
    covered = sorted(Path(k).name for k in manifest)
    assert on_disk == covered, "artifacts without a repro entry, or entries for deleted artifacts"


def test_manifest_entries_point_at_real_outputs() -> None:
    manifest = repro.load_manifest()
    for key, entry in manifest.items():
        base = ROOT / key
        assert base.is_dir(), key
        for step in entry["steps"]:
            assert step["argv"], key
            for group in ("byte", "structure"):
                for rel in step.get(group, []):
                    assert (base / rel).is_file(), f"{key} {rel} listed as {group} but not committed"


@pytest.mark.parametrize("unknown", ["artifacts", "tools"])
def test_unknown_directory_has_no_entry(unknown: str) -> None:
    assert repro.entry_for(ROOT / unknown, repro.load_manifest()) is None


def test_gate_g3_fails_without_a_manifest_entry(tmp_path: Path) -> None:
    import gate

    art = tmp_path / "unlisted"
    (art / "results").mkdir(parents=True)
    (art / "results" / "summary.json").write_text("{}\n", encoding="utf-8")
    ok, detail = gate.check_reproducible(art)
    assert not ok
    assert "no entry in tools/repro_manifest.json" in detail


def test_gate_g3_fails_when_a_number_was_edited(tmp_path: Path) -> None:
    import gate

    art = make_artifact(tmp_path)
    monkeypatch_entry = dict(ENTRY)
    (art / "results" / "summary.json").write_text(
        json.dumps({"net": 9999, "trades": 7}, indent=2) + "\n", encoding="utf-8"
    )
    real_entry_for = gate.repro.entry_for
    gate.repro.entry_for = lambda base, manifest: monkeypatch_entry
    try:
        ok, detail = gate.check_reproducible(art)
    finally:
        gate.repro.entry_for = real_entry_for
    assert not ok
    assert "results do not reproduce" in detail
