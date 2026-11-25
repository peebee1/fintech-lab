"""The bench output: what the README is allowed to quote, and where it is written."""

import json

from cashplan.bench import inr, render_markdown, summary_lines, write_results


def test_every_check_passes(summary):
    failed = {name: value for name, value in summary["checks"].items() if not value}
    assert failed == {}


def test_the_headline_numbers_are_present(summary):
    by_name = {row["policy"]: row for row in summary["policies"]}
    best = by_name["minmax_3_6"]
    weekly = by_name["fixed_week_capacity"]
    assert best["total_paise"] < weekly["total_paise"]
    assert best["service_level"] == 1.0
    assert weekly["service_level"] < 1.0
    assert summary["oracle_gap_paise"] > 0
    assert summary["book"]["notes"] > 0
    assert summary["book"]["value_paise"] == summary["book"]["notes"] * summary["book"]["note_paise"]


def test_the_service_target_is_met_and_it_is_the_cheap_policy(summary):
    assert summary["service_target"] == 0.995
    assert summary["best_compliant"] == summary["cheapest_practical"]
    assert summary["service_premium_paise"] == 0


def test_both_sweeps_print_five_rungs(summary):
    assert [row["cassettes"] for row in summary["capacity_sweep_fixed"]] == [2, 3, 4, 5, 6]
    assert [row["cassettes"] for row in summary["capacity_sweep_headline"]] == [2, 3, 4, 5, 6]
    assert all(row["total_paise"] > 0 for row in summary["capacity_sweep_fixed"])


def test_the_markdown_has_no_dash_punctuation(summary):
    text = render_markdown(summary)
    assert "\u2014" not in text and "\u2013" not in text
    assert "| Policy |" in text


def test_summary_lines_name_the_numbers(summary):
    by_name = {row["policy"]: row for row in summary["policies"]}
    cheapest = by_name[summary["cheapest_practical"]]
    lines = summary_lines(summary)
    assert len(lines) >= 3
    assert any("cheapest practical" in line and inr(cheapest["total_paise"]) in line for line in lines)


def test_the_comparisons_reconcile(summary):
    by_name = {row["policy"]: row for row in summary["policies"]}
    best = by_name[summary["cheapest_practical"]]
    weekly = by_name["fixed_week_capacity"]
    comparisons = summary["comparisons"]
    assert comparisons["weekly_extra_paise"] == weekly["total_paise"] - best["total_paise"]
    assert comparisons["best_bps_of_value"] > 0
    assert 15 < comparisons["weekly_extra_pct_of_best"] < 18
    assert 10 < comparisons["oracle_gap_pct_of_best"] < 14
    assert comparisons["metro_share_of_weekly_lost_pct"] > 95
    assert comparisons["fixed_first_compliant_rung"] == 5
    assert comparisons["fixed_compliant_pct_above_best"] > 40
    assert comparisons["calendar_lost_withdrawals"] == by_name["calendar_two_runs"]["lost_withdrawals"]


def test_writing_twice_into_a_scratch_directory_is_byte_identical(summary, tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    write_results(first, summary)
    write_results(second, summary)
    for name in ("summary.json", "summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    payload = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    assert payload["checks"]["conservation_and_capacity"] is True


def test_the_default_writer_is_resolved_at_call_time(tmp_path, monkeypatch):
    import cashplan.bench as bench

    monkeypatch.setattr(bench, "RESULTS", tmp_path / "elsewhere")
    target = bench.write_results(summary=bench.build(seed=3, days=20))
    assert target == tmp_path / "elsewhere"
    assert (target / "summary.json").exists()
