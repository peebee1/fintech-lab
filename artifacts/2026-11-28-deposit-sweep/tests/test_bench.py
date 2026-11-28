"""The bench: the committed numbers, and where they are allowed to be written."""

import hashlib
import json
from pathlib import Path

from depositsweep.bench import run
from depositsweep.cli import dollars, render_markdown, write_results

ROOT = Path(__file__).resolve().parents[1]


def test_every_check_passes(summary):
    failed = [c for c in summary["checks"] if not c["ok"]]
    assert failed == []


def test_the_policy_names_are_stable(summary):
    names = [p["policy"] for p in summary["policies"]]
    assert names == ["yield_only", "capped_1", "capped_3", "even", "capped_12"]


def test_the_sweep_covers_eight_rungs_and_ends_flat(summary):
    sweep = summary["sweep"]
    assert [row["max_links"] for row in sweep] == list(range(1, 9))
    tail = {row["uninsured_cents"] for row in sweep[-3:]}
    assert tail == {0}, "every rung past the largest balance must be flat and zero"


def test_the_first_rung_is_the_same_policy_as_yield_only(summary):
    """A one link cap with a residual sweep is the cap blind default, not a repair."""
    first = summary["sweep"][0]
    yield_only = summary["policies"][0]
    assert first["uninsured_cents"] == yield_only["uninsured_cents"]
    assert first["interest_cents"] == yield_only["interest_cents"]


def test_the_cap_costs_links_and_not_yield_on_the_large_book(summary):
    yield_only = summary["policies"][0]
    capped = summary["policies"][2]
    assert capped["interest_cents"] == yield_only["interest_cents"]
    assert capped["links"] > yield_only["links"]
    assert capped["uninsured_cents"] < yield_only["uninsured_cents"]


def test_equal_split_pays_more_links_for_the_same_protection(summary):
    even = summary["policies"][3]
    oracle = summary["policies"][4]
    assert even["uninsured_cents"] == oracle["uninsured_cents"] == 0
    assert even["links"] > 3 * oracle["links"]


def test_the_book_numbers_are_plausible_for_a_program_book(summary):
    book = summary["book"]
    assert book["customers"] == 1500
    assert 40_000_000_00 < book["total_cents"] < 60_000_000_00
    assert book["median_cents"] < book["mean_cents"] < book["max_cents"]
    assert 0 < book["top5pct_share_bps"] < 3_500


def test_the_small_book_is_where_the_invariance_breaks(summary):
    small = summary["small_book_test"]
    assert small["total_cents"] < 3_000_000_00
    assert small["capped_3_interest_cents"] < small["yield_only_interest_cents"]
    assert small["capped_3_uninsured_cents"] < small["yield_only_uninsured_cents"]


def test_markdown_quotes_the_same_interest_as_the_json(summary):
    text = render_markdown(summary)
    assert dollars(summary["policies"][0]["interest_cents"]) in text
    assert "## Where the invariance breaks" in text
    assert "FAIL" not in text


def test_write_results_is_byte_stable_and_leaves_results_alone(tmp_path):
    committed = ROOT / "results"
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in committed.iterdir()
        if p.is_file()
    }

    write_results(tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    write_results(tmp_path)
    second = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}

    assert first == second
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in committed.iterdir()
        if p.is_file()
    }
    assert before == after


def test_the_json_payload_is_json_serialisable_and_integer_cents(summary):
    text = json.dumps(summary)
    loaded = json.loads(text)
    assert loaded["book"]["total_cents"] == summary["book"]["total_cents"]
    assert all(isinstance(p["interest_cents"], int) for p in loaded["policies"])
