"""Pins the numbers the README quotes, and proves results/ is reproducible from code."""

import json
from pathlib import Path

from fxalloc import bench

ARTIFACT = Path(__file__).resolve().parents[1]
RESULTS = ARTIFACT / "results"
FILES = ("allocation.json", "bias.json", "fx_order.json", "invariants.json", "example.json")


def test_bench_is_deterministic():
    first = bench.run_all()
    second = bench.run_all()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_headline_allocation_numbers():
    allocation = bench.run_all()["allocation"]["methods"]
    assert allocation["largest_remainder"]["mismatched"] == 0
    assert allocation["floor_to_largest"]["mismatched"] == 0
    assert allocation["naive_half_up"]["mismatched"] == 621
    assert allocation["naive_half_up"]["mismatch_pct"] == 20.7
    assert allocation["naive_half_up"]["max_abs_residual"] == 2
    assert allocation["naive_half_even"]["mismatched"] == 622


def test_no_method_ever_fails_reconciliation():
    for name, stats in bench.run_all()["allocation"]["methods"].items():
        assert stats["reconciliation_violations"] == 0, name


def test_headline_fx_order_numbers():
    order = bench.run_all()["fx_order"]
    assert order["payouts"] == bench.TRIALS
    assert order["disagreed"] == 988
    assert order["disagreed_pct"] == 32.93
    assert order["max_abs_gap"] == 2
    for block in order["by_target"].values():
        assert block["disagreed"] > 0


def test_overpayment_bias_is_measured_not_assumed():
    bias = bench.run_all()["bias"]["methods"]
    assert bias["largest_remainder"]["max_excess_minor"] < 1
    assert bias["floor_to_largest"]["max_excess_minor"] > 1
    assert bias["floor_to_largest"]["largest_party_overpaid_pct"] > 90
    assert bias["floor_to_largest"]["mean_excess_bps"] > 0.5
    assert abs(bias["largest_remainder"]["mean_excess_bps"]) < 0.1


def test_exhaustive_invariants_hold():
    invariants = bench.run_all()["invariants"]
    assert invariants["cases"] == 3374
    balanced = invariants["largest_remainder"]
    assert balanced["total_violations"] == 0
    assert balanced["deviation_violations"] == 0
    assert balanced["reconciliation_violations"] == 0
    assert balanced["zero_weight_violations"] == 0
    assert balanced["worst_party_deviation"] < 1
    assert invariants["naive_half_up"]["unbalanced_cases"] == 1571


def test_worked_example_matches_the_readme():
    example = bench.small_example()
    by_method = {row["method"]: row for row in example["rows"]}
    assert by_method["largest_remainder"]["sum"] == 10_000
    assert by_method["naive_half_up"]["sum"] == 9_999
    assert by_method["naive_half_up"]["parts"] == [3333, 3333, 3333]


def test_committed_results_reproduce(tmp_path):
    """CI regenerates results/ and fails the build if the committed numbers moved."""
    bench.write_results(tmp_path)
    for name in FILES:
        committed = json.loads((RESULTS / name).read_text(encoding="utf-8"))
        fresh = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert committed == fresh, name
    assert (RESULTS / "summary.md").read_text(encoding="utf-8") == (
        tmp_path / "summary.md"
    ).read_text(encoding="utf-8")


def test_results_cover_every_experiment():
    for name in FILES:
        assert (RESULTS / name).is_file(), name
    summary = (RESULTS / "summary.md").read_text(encoding="utf-8")
    for heading in (
        "Allocation over synthetic payouts",
        "Who gets the benefit",
        "Convert then split against split then convert",
        "Exhaustive invariants",
        "One worked example",
    ):
        assert heading in summary
