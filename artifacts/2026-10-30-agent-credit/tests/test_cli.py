import json

from creditnet import cli, sim


def test_cli_writes_every_result_file(tmp_path) -> None:
    payload = cli.write_results(tmp_path, scenarios=3)
    expected = {"summary.json", "netting.json", "limits.json", "default.json", "policies.json", "summary.md"}
    assert {path.name for path in tmp_path.iterdir()} == expected
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["meta"]["scenarios"] == 3
    assert summary["meta"]["synthetic"] is True
    assert summary["netting"]["gross_value"] == payload["netting"]["gross_value"]


def test_results_are_byte_identical_on_rerun(tmp_path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    cli.write_results(first, scenarios=2)
    cli.write_results(second, scenarios=2)
    for name in ("summary.json", "netting.json", "limits.json", "default.json", "policies.json", "summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_summary_markdown_quotes_the_numbers(tmp_path) -> None:
    payload = cli.write_results(tmp_path, scenarios=3)
    text = (tmp_path / "summary.md").read_text()
    assert "multilateral netting" in text
    assert payload["meta"]["reference_limit_display"] in text
    assert "gross flow" in text


def test_committed_results_match_a_fresh_run() -> None:
    """The numbers in results/ on disk are what the committed code produces today."""
    committed = json.loads((cli.RESULTS / "summary.json").read_text())
    fresh = sim.experiments()
    assert committed["netting"] == fresh["netting"]
    assert committed["sweep"] == fresh["sweep"]


def test_cli_main_bench_prints_summary(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "RESULTS", tmp_path)
    cli.main(["bench", "--scenarios", "2"])
    out = capsys.readouterr().out
    assert "gross flow" in out
    assert (tmp_path / "summary.json").exists()
