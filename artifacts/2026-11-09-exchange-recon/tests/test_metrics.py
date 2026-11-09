import random

from orderrecon import metrics
from orderrecon.model import Break


def test_score_counts_exact_class_and_key():
    truth = [{"class": "missing_fill", "key": "O1"}]
    breaks = [
        Break("missing_fill", "O1"),
        Break("missing_fill", "O2"),
        Break("broker_qty_lag", "O3"),
    ]
    scored = metrics.score(truth, breaks)
    assert scored["correct"] == 1
    assert scored["precision"] == round(1 / 3, 4)
    assert scored["recall"] == 1.0


def test_wrong_class_is_not_a_match():
    truth = [{"class": "qty_mismatch", "key": "O1"}]
    breaks = [Break("duplicate_fill", "O1")]
    scored = metrics.score(truth, breaks)
    assert scored["correct"] == 0
    assert scored["f1"] == 0.0


def test_triage_covers_everything_with_a_full_budget():
    breaks = [Break("missing_fill", f"O{i}", impact=100 * (i + 1)) for i in range(10)]
    result = metrics.triage(breaks, budget=10, rng=random.Random(1))
    assert result["coverage_by_impact"] == 1.0
    assert result["breaks"] == 10


def test_triage_budget_binds():
    breaks = [Break("missing_fill", f"O{i}", impact=100 * (i + 1)) for i in range(100)]
    result = metrics.triage(breaks, budget=10, rng=random.Random(1))
    assert result["coverage_by_impact"] < 1.0
    assert result["coverage_by_impact"] >= result["coverage_by_arrival"]
    assert result["coverage_by_impact"] >= result["coverage_random"]


def test_triage_on_one_ticket_takes_the_largest():
    breaks = [Break("missing_fill", "small", impact=10), Break("missing_fill", "big", impact=90)]
    result = metrics.triage(breaks, budget=1, rng=random.Random(1))
    assert result["coverage_by_impact"] == 0.9
    assert result["top_ten_share"] == 1.0


def test_empty_breaks_do_not_divide_by_zero():
    result = metrics.triage([], budget=60)
    assert result["coverage_by_impact"] == 0.0
    assert result["impact_paise"] == 0
