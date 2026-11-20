import json

from qualification.bench import build, render_markdown, write_results


def test_results_are_byte_identical_across_runs(tmp_path):
    write_results(tmp_path)
    first_json = (tmp_path / "summary.json").read_bytes()
    first_md = (tmp_path / "summary.md").read_bytes()
    write_results(tmp_path)
    assert (tmp_path / "summary.json").read_bytes() == first_json
    assert (tmp_path / "summary.md").read_bytes() == first_md


def test_default_directory_is_resolved_inside_the_call(tmp_path, monkeypatch):
    import qualification.bench as bench

    monkeypatch.setattr(bench, "RESULTS", tmp_path)
    write_results()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.md").exists()


def test_committed_results_match_the_code():
    from qualification.bench import RESULTS

    committed = json.loads((RESULTS / "summary.json").read_text())
    current = build()
    assert committed["headline"] == current["headline"]
    assert committed["totals"] == current["totals"]
    assert committed["book"] == current["book"]


def test_payload_states_the_gap_and_its_partition():
    payload = build()
    head = payload["headline"]
    assert payload["synthetic"] is True
    assert head["gap_cents"] == payload["totals"]["gap_cents"]
    assert sum(c["gap_cents"] for c in payload["by_cause"]) == head["gap_cents"]
    assert head["best_pair_share"] > head["best_single_share"] > 0
    assert head["cascade_cents"] > 0
    assert head["all_fixes_cents"] == head["gap_cents"]


def test_the_stress_book_holds_the_same_volume_and_a_smaller_gap():
    payload = build()
    stress = payload["stress"]
    assert stress["processed_cents"] == payload["book"]["processed_cents"]
    assert 0 < stress["gap_cents"] < payload["headline"]["gap_cents"]
    assert stress["best_pair_share"] > 0


def test_markdown_states_the_numbers_it_computed():
    payload = build()
    text = render_markdown(payload)
    for needle in (
        "Synthetic book",
        "Gap by the rule that binds",
        "Repair budget",
        "negotiated rate",
        "Stress",
        payload["by_cause"][1]["code"],
    ):
        assert needle in text
    assert f"{payload['book']['transactions']:,} transactions" in text


def test_show_output_quotes_the_same_numbers_as_the_bench():
    from qualification.bench import summarise

    lines = "\n".join(summarise(build()))
    head = build()["headline"]
    assert "commercial_data" in lines or head["top_cause"] in lines
    assert "rate cut" in lines
