"""The documented command runs and says something falsifiable."""

from fxalloc import cli


def test_split_prints_every_method(capsys):
    cli.main(["split", "10000", "USD", "1", "1", "1"])
    out = capsys.readouterr().out
    for name in ("largest_remainder", "floor_to_largest", "naive_half_up", "naive_half_even"):
        assert name in out
    assert "balanced" in out
    assert "off by 1 minor units" in out
    assert "100.00 USD" in out


def test_split_handles_a_currency_without_minor_units(capsys):
    cli.main(["split", "101", "JPY", "1", "2", "3"])
    out = capsys.readouterr().out
    assert "101 JPY" in out
    assert "balanced" in out


def test_reconciliation_command_does_not_touch_results(capsys):
    before = cli.RESULTS.joinpath("summary.md").read_text(encoding="utf-8")
    cli.main(["split", "7", "KWD", "1", "1"])
    capsys.readouterr()
    after = cli.RESULTS.joinpath("summary.md").read_text(encoding="utf-8")
    assert before == after
