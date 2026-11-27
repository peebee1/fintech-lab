"""The bench output: what the README is allowed to quote, and where it is written."""

import hashlib
import json
from pathlib import Path

from payoutholds.bench import build, render_markdown, summary_lines, usd, write_results

ROOT = Path(__file__).resolve().parents[1]


def test_every_check_passes(summary):
    failed = {name: value for name, value in summary["checks"].items() if not value}
    assert failed == {}


def test_the_ladder_names_are_stable(summary):
    assert set(summary["policies"]) == {
        "pay_t1",
        "hold_7",
        "hold_14",
        "hold_21",
        "reserve_5",
        "reserve_10",
        "reserve_20",
        "hold_7_reserve_10",
        "reserve_10_no_clawback",
        "tiered_hold",
        "tiered_reserve",
    }


def test_more_reserve_never_increases_the_write_off(summary):
    sweep = summary["sweeps"]["reserve"]
    assert all(a["totals"]["written_off"] >= b["totals"]["written_off"] for a, b in zip(sweep, sweep[1:]))


def test_the_reserve_sweep_has_an_interior_minimum(summary):
    economics = [row["totals"]["economic_cost_cents"] for row in summary["sweeps"]["reserve"]]
    assert economics.index(min(economics)) not in (0, len(economics) - 1)


def test_each_further_rung_of_reserve_buys_less(summary):
    rungs = summary["marginal_reserve"]
    saved = [rung["writeoff_saved_cents"] for rung in rungs]
    assert saved == sorted(saved, reverse=True)
    assert rungs[-1]["net_cents"] < rungs[0]["net_cents"]


def test_a_reserve_is_cheaper_than_the_hold_that_protects_less(summary):
    """The claim the README makes: the hold loses on both counts."""
    reserve = summary["policies"]["reserve_10"]["totals"]
    hold = summary["policies"]["hold_14"]["totals"]
    assert reserve["written_off"] < hold["written_off"]
    assert reserve["float_cost_cents"] < hold["float_cost_cents"]


def test_the_banded_policies_do_not_beat_the_blunt_reserve(summary):
    """A measured negative result, pinned so a parameter change has to re-open it."""
    comp = summary["comparisons"]
    assert comp["tiered_vs_best_flat_cents"] > 0
    assert comp["tiered_reserve_vs_best_flat_cents"] > 0


def test_clawback_is_worth_real_money(summary):
    assert summary["comparisons"]["clawback_value_cents"] > 0


def test_the_oracle_is_the_floor(summary):
    oracle = summary["oracle"]["totals"]["economic_cost_cents"]
    assert all(row["totals"]["economic_cost_cents"] >= oracle for row in summary["policies"].values())


def test_the_best_policy_captures_less_than_the_whole_prize(summary):
    assert 0 < summary["comparisons"]["prize_captured_pct"] < 100


def test_usd_formats_cents():
    assert usd(123456) == "$1,234.56"
    assert usd(0) == "$0.00"


def test_lean_summary_carries_no_per_seller_rows(summary):
    for result in summary["policies"].values():
        assert "rows" not in result


def test_summary_lines_quote_the_digest(summary):
    lines = summary_lines(summary)
    assert len(lines) == 5
    assert any(summary["book"]["digest"] in line for line in lines)


def test_markdown_has_the_three_tables_and_a_check_verdict(summary):
    text = render_markdown(summary)
    assert text.count("|---") >= 3
    assert "All checks pass." in text
    assert "oracle" in text


def test_write_results_writes_where_it_is_told_and_twice_identically(tmp_path):
    summary = build()
    first = tmp_path / "one"
    second = tmp_path / "two"
    write_results(first, summary)
    write_results(second, summary)
    for name in ("summary.json", "summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_write_results_does_not_touch_the_committed_results(tmp_path):
    committed = ROOT / "results" / "summary.json"
    before = hashlib.sha256(committed.read_bytes()).hexdigest()
    write_results(tmp_path, build())
    after = hashlib.sha256(committed.read_bytes()).hexdigest()
    assert before == after
    payload = json.loads((tmp_path / "summary.json").read_text())
    assert payload["book"]["digest"] == json.loads(committed.read_text())["book"]["digest"]
