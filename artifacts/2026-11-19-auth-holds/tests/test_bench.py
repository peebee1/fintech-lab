import json

from authholds.bench import build, render_markdown, write_results


def test_results_are_byte_identical_across_runs(tmp_path):
    write_results(tmp_path, build())
    first_json = (tmp_path / "summary.json").read_bytes()
    first_md = (tmp_path / "summary.md").read_bytes()
    write_results(tmp_path, build())
    assert (tmp_path / "summary.json").read_bytes() == first_json
    assert (tmp_path / "summary.md").read_bytes() == first_md


def test_default_directory_is_resolved_inside_the_call(tmp_path, monkeypatch):
    import authholds.bench as bench

    monkeypatch.setattr(bench, "RESULTS", tmp_path)
    write_results()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.md").exists()


def test_payload_carries_the_sweeps_and_a_consistent_headline():
    payload = build()
    assert len(payload["expiry_sweep"]) == 9
    assert len(payload["tolerance_sweep"]) == 6
    assert payload["synthetic"] is True
    assert payload["book"]["by_kind"]["hotel"] > 0
    head = payload["headline"]
    default_row = next(r for r in payload["expiry_sweep"] if r["expiry_days"] == head["default_expiry_days"])
    assert default_row["capture_rate"] == head["default_capture_rate"]
    refused = [r["refused_expired_cents"] for r in payload["expiry_sweep"]]
    assert refused == sorted(refused, reverse=True)
    assert all(r["invariant_ok"] for r in payload["expiry_sweep"])
    assert all(r["refused_unknown_cents"] == 0 for r in payload["expiry_sweep"])


def test_markdown_states_the_numbers_it_computed():
    payload = build()
    text = render_markdown(payload)
    assert "Expiry sweep" in text
    assert "Tolerance sweep" in text
    assert "Synthetic book" in text
    assert f"{payload['book']['authorisations']} authorisations" in text


def test_committed_results_match_the_code():
    from authholds.bench import RESULTS

    committed = json.loads((RESULTS / "summary.json").read_text())
    assert committed["headline"] == build()["headline"]
    assert committed["book"]["requested_cents"] == build()["book"]["requested_cents"]
