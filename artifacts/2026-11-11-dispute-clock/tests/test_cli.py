import json

from disputeclock import bench, cli


def test_results_are_reproducible_into_a_temp_directory(tmp_path):
    first = cli.write_results(directory=tmp_path / "one", seed=13, n=300, horizon=360, budget=40)
    second = cli.write_results(directory=tmp_path / "two", seed=13, n=300, horizon=360, budget=40)
    assert first == second
    for name in ("summary.json", "summary.md"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()


def test_writing_never_touches_the_committed_results(tmp_path):
    committed = cli.RESULTS / "summary.json"
    before = committed.read_bytes()
    cli.write_results(directory=tmp_path, seed=13, n=60, horizon=360, budget=40)
    assert committed.read_bytes() == before


def test_cli_prints_the_table(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "RESULTS", tmp_path)
    cli.main(["run", "--cases", "800", "--seed", "13", "--budget", "16"])
    out = capsys.readouterr().out
    assert "three_clock" in out
    assert "checks:" in out


def test_summary_json_carries_the_schema(tmp_path):
    cli.write_results(directory=tmp_path, seed=13, n=800, horizon=360, budget=16)
    payload = json.loads((tmp_path / "summary.json").read_text())
    assert payload["schema"] == "dispute-clock/1"
    assert len(payload["policies"]) == len(bench.LADDER)
    assert payload["passed"] is True
