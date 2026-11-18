"""The bench: committed numbers, the ordering it claims, and byte stable output."""

from __future__ import annotations

import json

from liquidity.bench import run_bench


def rows_by_name(payload: dict) -> dict:
    return {row["policy"]: row for row in payload["policies"]}


def test_committed_results_pass_every_check(committed: dict):
    assert committed["checks"]
    failed = [name for name, ok in committed["checks"].items() if not ok]
    assert failed == []
    assert committed["eval_days"] == 660
    assert committed["book"]["days"] == 720


def test_the_ladder_is_ordered_the_way_the_claim_says(committed: dict):
    rows = rows_by_name(committed)
    assert rows["zero"]["annual_total_usd"] > rows["daily_net_p95"]["annual_total_usd"]
    assert rows["daily_net_p95"]["annual_total_usd"] > rows["gross_batch"]["annual_total_usd"]
    assert rows["gross_batch"]["annual_total_usd"] > rows["peak_p90"]["annual_total_usd"]
    assert rows["peak_p90"]["annual_total_usd"] < rows["peak_p95"]["annual_total_usd"]
    assert committed["oracle"]["annual_total_usd"] < rows["peak_p90"]["annual_total_usd"]


def test_the_daily_net_policy_is_the_straw_man_it_claims_to_be(committed: dict):
    """It holds real money, and it still misses almost every day."""
    rows = rows_by_name(committed)
    daily = rows["daily_net_p95"]
    assert daily["mean_opening_usd"] > 500_000
    assert daily["shortfall_rate"] > 0.9
    assert rows["peak_p90"]["shortfall_rate"] < 0.15


def test_every_net_positive_day_still_needed_cash(committed: dict):
    assert committed["net_positive_days"] > 300
    assert committed["net_positive_days_that_shorted"] == committed["net_positive_days"]


def test_shortfall_count_never_exceeds_two_batches_a_day(committed: dict):
    for row in committed["policies"] + [committed["oracle"]]:
        assert row["events"] <= 2 * row["days_shorted"] + 2 * (committed["eval_days"] - row["days_shorted"])


def test_the_percentile_sweep_has_an_interior_minimum(committed: dict):
    sweep = committed["sweep"]
    costs = [row["annual_total_usd"] for row in sweep]
    best = costs.index(min(costs))
    assert 0 < best < len(costs) - 1, "the optimum must not sit at either end of the sweep"
    assert sweep[best]["policy"] == "peak_p90"
    opens = [row["mean_opening_usd"] for row in sweep]
    assert opens == sorted(opens)


def test_the_fee_moves_the_optimum(committed: dict):
    fees = {row["fee_usd"]: row for row in committed["fee_sensitivity"]}
    assert fees[50.0]["best_policy"] == "peak_p75"
    assert fees[1000.0]["best_policy"] == "peak_p95"
    assert fees[50.0]["peak_p90_usd"] < fees[1000.0]["peak_p90_usd"] * 0.9


def test_the_window_is_not_the_lever(committed: dict):
    """Honest null: any window from 20 to 160 days lands within 2 percent."""
    costs = [w["annual_total_usd"] for w in committed["windows"]]
    assert max(costs) / min(costs) < 1.02


def test_rescheduling_the_settlement_beats_resizing_the_buffer(committed: dict):
    regimes = {r["regime"]: r for r in committed["regimes"]}
    base = rows_by_name(regimes["baseline"])
    retimed = rows_by_name(regimes["settlement at the open"])
    saving = base["peak_p90"]["annual_total_usd"] - retimed["peak_p90"]["annual_total_usd"]
    assert saving > 50_000
    assert retimed["zero"]["annual_total_usd"] < 0.2 * base["zero"]["annual_total_usd"]


def test_two_writes_produce_identical_bytes(tmp_path):
    run_bench(tmp_path)
    first = (tmp_path / "summary.json").read_bytes()
    run_bench(tmp_path)
    assert (tmp_path / "summary.json").read_bytes() == first
    assert json.loads(first)["checks"]["every_eval_day_scored"] is True


def test_a_small_run_still_produces_the_same_shape(tmp_path):
    payload = run_bench(tmp_path, fee_cents=5_000)
    assert payload["fee_per_failed_batch_usd"] == 50.0
    assert {row["policy"] for row in payload["policies"]} == {
        "zero",
        "daily_net",
        "daily_net_p95",
        "gross_batch",
        "peak_p50",
        "peak_p75",
        "peak_p90",
        "peak_p95",
        "peak_p100",
    }
