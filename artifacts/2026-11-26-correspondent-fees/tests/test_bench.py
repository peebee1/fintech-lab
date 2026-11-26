"""The bench output: what the README is allowed to quote, and where it is written."""

import json
from pathlib import Path

from corrfee import bench
from corrfee.bench import build, render_markdown, summary_lines, usd, write_results
from corrfee.book import expected_bps, generate
from corrfee.fees import our_fee, sha_fee

ROOT = Path(__file__).resolve().parents[1]


def test_every_check_passes(summary):
    failed = {name: value for name, value in summary["checks"].items() if not value}
    assert failed == {}


def test_the_headline_relationship_is_what_the_readme_claims(summary):
    cmp = summary["comparisons"]
    assert cmp["sha_sender_bps"] < cmp["our_sender_bps"], "SHA is cheaper on the payer's ledger"
    assert cmp["sha_economic_bps"] > cmp["our_economic_bps"], "and dearer once the supplier counts"
    assert cmp["sha_supplier_bps"] > 0
    assert summary["book"]["deduction_bps"] == cmp["sha_supplier_bps"]


def test_the_ladder_has_nine_distinct_policies(summary):
    names = [row["policy"] for row in summary["policies"]]
    assert len(names) == len(set(names)) == 9
    assert "oracle" in names and "our_all" in names


def test_the_best_practical_policy_is_not_the_oracle(summary):
    cmp = summary["comparisons"]
    assert cmp["best_economic_policy"] != "oracle"
    assert cmp["oracle_economic_bps"] <= cmp["best_economic_bps"]
    assert cmp["oracle_prize_cents"] > 0


def test_repairing_costs_more_than_the_shortfall_it_fixes(summary):
    by_name = {row["policy"]: row for row in summary["policies"]}
    assert by_name["sha_repair_all"]["economic_bps"] > by_name["sha_none"]["economic_bps"]
    cmp = summary["comparisons"]
    assert cmp["repair_fee_at_median_cents"] > cmp["claim_median_cents"] * 0.5


def test_the_claim_sweep_has_one_row_per_threshold_plus_never(summary):
    sweep = summary["claim_threshold_sweep"]
    assert len(sweep) == len(bench.CLAIM_THRESHOLDS) + 1
    assert sweep[-1]["threshold_cents"] is None
    repairs = [row["repairs"] for row in sweep]
    assert repairs == sorted(repairs, reverse=True)


def test_the_tolerance_sweep_moves_the_claim_desk_only(summary):
    sweep = summary["tolerance_sweep"]
    assert len(sweep) == len(bench.TOLERANCES)
    assert sweep[0]["claims"] >= sweep[-1]["claims"]
    # Raising the tolerated deduction cuts admin cost and leaves the absorbed
    # value where it was, because the supplier was already carrying it.
    assert sweep[-1]["economic_bps"] <= sweep[0]["economic_bps"]


def test_the_breakeven_rule_holds_at_its_own_boundary(summary):
    book = generate()
    milli = {
        corridor.code: round(expected_bps(book)[corridor.code] * 1_000)
        for corridor in book.corridors
    }
    checked = 0
    for row in summary["breakeven"]:
        amount = row["breakeven_cents"]
        if amount is None:
            continue
        expected = amount * milli[row["corridor"]] // 10_000_000
        assert our_fee(amount) < sha_fee(amount) + expected
        assert our_fee(amount - 2_500) >= sha_fee(amount - 2_500) + (
            (amount - 2_500) * milli[row["corridor"]] // 10_000_000
        )
        checked += 1
    assert checked > 0


def test_the_markdown_has_no_dash_punctuation_and_has_the_tables(summary):
    text = render_markdown(summary)
    assert "\u2014" not in text and "\u2013" not in text
    assert "| Policy |" in text and "| Corridor |" in text


def test_the_markdown_quotes_only_rendered_values(summary):
    text = render_markdown(summary)
    first = summary["policies"][0]
    assert usd(first["sender_total_cents"]) in text
    assert str(summary["book"]["deduction_bps"]) in text


def test_summary_lines_name_the_two_ledgers(summary):
    lines = summary_lines(summary)
    assert any("SHA" in line and "supplier" in line for line in lines)
    assert any("OUR" in line for line in lines)


def test_writing_results_twice_is_byte_identical(tmp_path):
    first = write_results(tmp_path / "a")
    second = write_results(tmp_path / "b")
    assert first == tmp_path / "a"
    assert (tmp_path / "a" / "summary.json").read_bytes() == (
        tmp_path / "b" / "summary.json"
    ).read_bytes()
    assert (tmp_path / "a" / "summary.md").read_bytes() == (
        tmp_path / "b" / "summary.md"
    ).read_bytes()
    assert second.exists()


def test_writing_to_a_scratch_directory_does_not_touch_committed_results(tmp_path):
    committed = ROOT / "results" / "summary.json"
    before = committed.read_bytes() if committed.exists() else None
    write_results(tmp_path, build(invoices=40, days=5))
    after = committed.read_bytes() if committed.exists() else None
    assert before == after
    payload = json.loads((tmp_path / "summary.json").read_text())
    assert payload["book"]["invoices"] == 40


def test_the_committed_results_describe_the_default_book(summary):
    committed = json.loads((ROOT / "results" / "summary.json").read_text())
    assert committed["book"] == summary["book"]
    assert committed["policies"] == summary["policies"]


def test_the_package_has_no_wall_clock():
    for path in (ROOT / "corrfee").glob("*.py"):
        text = path.read_text()
        assert "datetime.now" not in text, path.name
        assert "time.time" not in text, path.name
        assert "random.seed" not in text, path.name
