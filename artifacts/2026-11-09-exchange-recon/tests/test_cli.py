import json

from orderrecon import cli


def test_results_are_byte_identical_on_a_second_write(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    cli.write_results(directory=first, seed=11, n_orders=120)
    cli.write_results(directory=second, seed=11, n_orders=120)

    assert (first / "summary.json").read_bytes() == (second / "summary.json").read_bytes()
    assert (first / "summary.md").read_bytes() == (second / "summary.md").read_bytes()


def test_payload_has_the_measured_fields(tmp_path):
    payload = cli.write_results(directory=tmp_path, seed=11, n_orders=120)
    names = [row["policy"] for row in payload["policies"]]
    assert names == ["broker_only", "broker_vs_app", "stream_replay", "tape_three_way"]
    assert payload["invariants"]["max_share_gap"] == 0
    assert payload["invariants"]["cash_gap_paise"] == 0
    assert payload["triage"]["breaks"] == payload["session"]["injected_breaks"]

    written = json.loads((tmp_path / "summary.json").read_text())
    assert written == payload
    summary = (tmp_path / "summary.md").read_text()
    assert "tape_three_way" in summary
