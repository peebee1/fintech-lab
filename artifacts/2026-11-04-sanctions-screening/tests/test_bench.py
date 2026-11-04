import json

import pytest

from screenlab import bench, cli
from screenlab.model import Alert, Dataset, ListEntry, Subject


def entry(entry_id="SDN-001", name="Ahmed Haddad"):
    return ListEntry(entry_id=entry_id, name=name, aliases=(), dob="1979-04-12",
                     countries=("SY",), id_numbers=(), program="SDGT")


def subject(subject_id, truth=None, kind="clean"):
    return Subject(subject_id=subject_id, name=f"Person {subject_id}", dob="1979-04-12",
                   country="SY", national_id=f"ID{subject_id}", segment="retail",
                   truth_entry_id=truth, truth_kind=kind)


@pytest.fixture()
def tiny():
    subjects = (
        subject("C-1", "SDN-001", "exact"),
        subject("C-2", "SDN-001", "alias"),
        subject("C-3", None, "namesake"),
        subject("C-4"),
        subject("C-5"),
    )
    return Dataset(entries=(entry(),), subjects=subjects, seed=1)


def test_order_keeps_one_alert_per_customer_and_breaks_ties_by_id():
    alerts = [
        Alert(subject_id="C-3", entry_id="SDN-001", name_score=0.9, score=0.9, rule="name_only"),
        Alert(subject_id="C-1", entry_id="SDN-001", name_score=0.9, score=0.9, rule="name_only"),
        Alert(subject_id="C-1", entry_id="SDN-002", name_score=0.4, score=0.4, rule="name_only"),
    ]
    ordered = bench.order(alerts)
    assert [a.subject_id for a in ordered] == ["C-1", "C-3"]
    assert ordered[0].score == 0.9


def test_evaluate_counts_precision_recall_and_ranking_loss(tiny):
    alerts = [
        Alert(subject_id="C-1", entry_id="SDN-001", name_score=0.95, score=0.95, rule="name_exact_dob"),
        Alert(subject_id="C-2", entry_id="SDN-001", name_score=0.93, score=0.93, rule="name_close_dob"),
        Alert(subject_id="C-3", entry_id="SDN-001", name_score=0.92, score=0.92, rule="name_only"),
        Alert(subject_id="C-4", entry_id="SDN-001", name_score=0.5, score=0.5, rule="name_only"),
    ]
    tight = bench.evaluate(tiny, alerts, budget=2)
    assert tight["true_hits"] == 2
    assert tight["precision"] == 1.0
    assert tight["recall"] == 1.0
    assert tight["ranking_loss"] == 0
    assert tight["reviewed"] == 2

    loose = bench.evaluate(tiny, alerts, budget=3)
    assert loose["true_hits"] == 2
    assert loose["namesake_reviews"] == 1
    assert loose["precision"] == pytest.approx(2 / 3, abs=1e-4)


def test_the_budget_binds_and_is_never_exceeded(tiny):
    alerts = [
        Alert(subject_id=f"C-{i}", entry_id="SDN-001", name_score=0.5, score=0.5, rule="name_only")
        for i in range(1, 6)
    ]
    for budget in (1, 3, 5):
        row = bench.evaluate(tiny, alerts, budget=budget)
        assert row["reviewed"] == budget
        assert row["queued_customers"] == 5


def test_write_results_is_byte_stable_across_two_runs(tmp_path, tiny):
    first = tmp_path / "one"
    second = tmp_path / "two"
    cli.write_results(directory=first, budget=3, dataset=tiny)
    cli.write_results(directory=second, budget=3, dataset=tiny)
    for name in ("summary.json", "summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    payload = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    assert payload["meta"]["review_budget"] == 3
    assert payload["meta"]["book_size"] == 5


def test_results_path_resolves_at_call_time_not_import(tmp_path, monkeypatch, tiny):
    """A default argument of RESULTS silently ignores every monkeypatch."""
    monkeypatch.setattr(cli, "RESULTS", tmp_path)
    before = (bench.REVIEW_BUDGET,)
    cli.write_results(dataset=tiny)
    assert (tmp_path / "summary.json").exists()
    assert before == (bench.REVIEW_BUDGET,)
