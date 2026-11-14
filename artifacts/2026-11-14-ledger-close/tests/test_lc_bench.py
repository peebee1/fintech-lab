"""The bench must produce the same bytes twice, and every control must actually bite."""

import json

import pytest

from ledgerclose import bench
from ledgerclose import book as bookmod


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    target = tmp_path_factory.mktemp("bench")
    return bench.run(directory=target, seed=bench.SEED)


def test_two_runs_are_byte_identical(tmp_path):
    bench.run(directory=tmp_path / "one")
    bench.run(directory=tmp_path / "two")
    for name in ("summary.json", "summary.md"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()


def test_the_sealed_ledger_does_not_drift(payload):
    assert payload["sealed"]["closed_period_drift"]["periods_drifted"] == 0
    assert payload["sealed"]["closed_period_drift"]["absolute_minor"] == 0
    assert payload["sealed"]["closes_reproducing_before_tamper"] == len(payload["closed_periods"])


def test_the_baseline_drifts(payload):
    baseline = payload["baseline"]["closed_period_drift"]
    assert baseline["periods_drifted"] >= 2
    assert baseline["absolute_minor"] > 0
    assert payload["baseline"]["closes_reproducing"] < len(payload["closed_periods"])


def test_every_refusal_fires(payload):
    refusals = payload["sealed"]["refusals"]
    for rule in bench.RULES:
        assert refusals.get(rule, 0) >= 1, rule


def test_replay_appends_nothing_and_the_baseline_duplicates(payload):
    assert payload["sealed"]["replay_entries_appended"] == 0
    assert payload["baseline"]["duplicate_fee_minor"] < 0


def test_tamper_is_detected_and_one_close_stops_reproducing(payload):
    assert payload["sealed"]["chain"]["ok"] is False
    assert payload["sealed"]["chain"]["broken_seq"] == 1
    assert payload["sealed"]["closes_reproducing_after_tamper"] == len(payload["closed_periods"]) - 1
    assert payload["sealed"]["failing_closes"] == [payload["closed_periods"][0]]
    assert payload["baseline"]["tamper_detected"] == 0


def test_balance_sheet_holds(payload):
    assert payload["sealed"]["balanced_periods"] == payload["sealed"]["periods_tested"]
    assert payload["sealed"]["net_minor"] == 0
    assert payload["baseline"]["net_minor_after_events"] != 0


def test_a_run_elsewhere_does_not_touch_committed_results(tmp_path):
    """A default argument bound at import would overwrite results/ during a test run."""
    committed = bench.RESULTS / "summary.json"
    assert committed.exists()
    before = committed.read_bytes()
    bench.run(directory=tmp_path)
    assert committed.read_bytes() == before


def test_the_book_is_plausible():
    book = bookmod.build(seed=bench.SEED)
    assert book.net_minor() == 0
    assert all(sum(line.amount_minor for line in txn.lines) == 0 for txn in book)
    per_month = book.gross_minor / len(book.periods)
    assert 5_000_000 < per_month < 200_000_000, per_month
    assert 1_000_00 < book.gross_minor / book.payments < 1_00_000_00


def test_results_file_is_the_payload(tmp_path):
    bench.run(directory=tmp_path)
    written = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert written["artifact"] == "ledger-close"
    assert written["seed"] == bench.SEED
    assert written["book"]["counts"]["payment"] > 0
