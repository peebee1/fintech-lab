"""The bench: committed numbers, reproducibility, and the two things it must catch."""

from __future__ import annotations

import json

from consent.bench import run_bench


def test_committed_results_pass_every_check(committed: dict):
    assert committed["checks"], "results must carry a checks block"
    failed = [name for name, ok in committed["checks"].items() if not ok]
    assert failed == []
    assert committed["book"]["payers"] == 1200
    assert committed["book"]["scheduled_usd"] > 0


def test_committed_ladder_is_ordered_the_way_the_claim_says(committed: dict):
    rows = {row["policy"]: row for row in committed["policies"]}
    assert rows["never_refresh"]["capture_rate"] < rows["fixed_30"]["capture_rate"]
    assert rows["fixed_30"]["capture_rate"] < rows["on_failure"]["capture_rate"]
    assert rows["on_failure"]["capture_rate"] < rows["fixed_90"]["capture_rate"]
    assert rows["fixed_90"]["capture_rate"] < rows["jit_1"]["capture_rate"]
    assert rows["jit_1"]["capture_rate"] < rows["jit_3"]["capture_rate"]
    assert rows["jit_3"]["capture_rate"] > rows["jit_7"]["capture_rate"], "the optimum is inside the sweep"
    assert all(row["capture_rate"] <= 1.0 for row in rows.values())


def test_sweep_shows_the_cliff_at_the_context_window(committed: dict):
    sweep = {row["lead_days"]: row for row in committed["sweep"]}
    assert sweep[3]["contextual_share"] == 1.0
    assert sweep[4]["contextual_share"] == 0.0
    assert sweep[3]["capture_rate"] > sweep[4]["capture_rate"]
    refused = [sweep[lead]["refused"] for lead in range(1, 13)]
    assert refused[0] > refused[1] > refused[2], "a long lead recovers the slow responders"
    assert max(refused[5:]) <= 100, "past 6 days the tail is noise, not a slope"
    assert refused[0] > 10 * refused[6]


def test_two_writes_produce_identical_bytes(tmp_path):
    first = run_bench(directory=tmp_path / "one", size=60)
    second = run_bench(directory=tmp_path / "two", size=60)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert (tmp_path / "one" / "summary.json").read_bytes() == (tmp_path / "two" / "summary.json").read_bytes()
    assert (tmp_path / "one" / "summary.md").read_bytes() == (tmp_path / "two" / "summary.md").read_bytes()


def test_results_are_written_where_asked_not_into_the_repo(tmp_path):
    from consent import bench

    before = bench.RESULTS.joinpath("summary.json").read_bytes()
    run_bench(directory=tmp_path / "out", size=40)
    assert bench.RESULTS.joinpath("summary.json").read_bytes() == before
    assert (tmp_path / "out" / "summary.json").exists()
