import json

import pytest

from uwcal import cli, ingest


def test_read_predictions_accepts_a_space_before_a_quoted_field(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text('loan_id,pd\r\n1, "0.12"\r\n2,0.03\r\n', encoding="utf-8")
    assert ingest.read_predictions(path) == [(1, 0.12), (2, 0.03)]


def test_read_predictions_rejects_a_wrong_header(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text("id,probability\n1,0.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        ingest.read_predictions(path)


def test_read_predictions_rejects_a_short_row(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text("loan_id,pd\n1,0.2,extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected 2 fields"):
        ingest.read_predictions(path)


def test_read_predictions_rejects_a_duplicate_id(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text("loan_id,pd\n1,0.2\n1,0.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        ingest.read_predictions(path)


def test_read_predictions_rejects_out_of_range(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text("loan_id,pd\n1,12\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        ingest.read_predictions(path)


def test_read_predictions_rejects_an_empty_file(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        ingest.read_predictions(path)


def test_align_refuses_partial_coverage(parts, card):
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    pairs = [(loan.loan_id, p) for loan, p in zip(holdout[:-1], preds[:-1])]
    with pytest.raises(ValueError, match="no prediction"):
        ingest.align(pairs, holdout)


def test_align_returns_loan_order(parts, card):
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    shuffled = list(reversed(list(zip([loan.loan_id for loan in holdout], preds))))
    assert ingest.align(shuffled, holdout) == pytest.approx(preds)


def test_score_file_reports_metrics_and_policy(tmp_path, parts, card):
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    path = tmp_path / "preds.csv"
    path.write_text(
        "loan_id,pd\n" + "".join(f"{loan.loan_id},{p:.8f}\n" for loan, p in zip(holdout, preds)),
        encoding="utf-8",
    )
    report = cli.score_file(path, n=1200)
    assert 0.5 < report["auc"] < 1.0
    assert report["brier"] > 0.0
    assert "value" in report["policy"]
    assert report["policy"]["approved"] > 0


def test_write_results_is_byte_identical_across_runs(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    cli.write_results(first, n=1200)
    cli.write_results(second, n=1200)
    for name in ("summary.json", "summary.md", "reliability_overconfident.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_write_results_writes_into_tmp_not_the_committed_directory(tmp_path, parts):
    committed = cli.RESULTS / "summary.json"
    before = committed.read_bytes() if committed.exists() else None
    cli.write_results(tmp_path, n=1200)
    after = committed.read_bytes() if committed.exists() else None
    assert before == after
    assert (tmp_path / "summary.json").exists()


def test_summary_payload_claims_are_internally_consistent(tmp_path):
    payload = cli.write_results(tmp_path, n=1200)
    h = payload["headline"]
    assert h["auc_identical"] is True
    assert h["brier_overconfident"] > h["brier_calibrated"]
    assert h["brier_overconfident_recalibrated"] < h["brier_overconfident"]
    assert h["ece_overconfident_recalibrated"] < h["ece_overconfident"]
    assert payload["provenance"]["data"] == "synthetic"
    json.dumps(payload)
