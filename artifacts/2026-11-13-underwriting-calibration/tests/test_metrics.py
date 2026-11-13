import math

import pytest

from uwcal import metrics
from uwcal.models import temper


def test_brier_hand_computed():
    preds = [0.9, 0.1, 0.4]
    labels = [1, 0, 1]
    expected = ((0.9 - 1) ** 2 + (0.1 - 0) ** 2 + (0.4 - 1) ** 2) / 3
    assert metrics.brier(preds, labels) == pytest.approx(expected, abs=1e-15)


def test_brier_bounds():
    assert metrics.brier([1.0, 0.0], [1, 0]) == 0.0
    assert metrics.brier([0.0, 1.0], [1, 0]) == 1.0
    assert metrics.brier([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_brier_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        metrics.brier([0.5], [])


def test_auc_perfect_and_inverted():
    labels = [0, 0, 1, 1]
    assert metrics.auc([0.1, 0.2, 0.8, 0.9], labels) == 1.0
    assert metrics.auc([0.9, 0.8, 0.2, 0.1], labels) == 0.0


def test_auc_all_ties_is_a_coin_flip():
    assert metrics.auc([0.4] * 6, [0, 1, 0, 1, 0, 1]) == pytest.approx(0.5)


def test_auc_hand_computed_with_ties():
    # one tie block at 0.5: the positive in the block wins half its pair.
    preds = [0.1, 0.5, 0.5, 0.9]
    labels = [0, 0, 1, 1]
    assert metrics.auc(preds, labels) == pytest.approx(3.5 / 4.0)


def test_auc_needs_both_classes():
    with pytest.raises(ValueError):
        metrics.auc([0.2, 0.3], [0, 0])


def test_auc_is_blind_to_a_monotone_map(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    base = metrics.auc(preds, labels)
    assert metrics.auc([temper(p, 2.1) for p in preds], labels) == pytest.approx(base, abs=1e-12)
    assert metrics.auc([temper(p, 0.55) for p in preds], labels) == pytest.approx(base, abs=1e-12)


def test_murphy_decomposition_reconstructs_brier_exactly(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    exact = metrics.murphy(preds, labels)
    assert exact.within_bin == pytest.approx(0.0, abs=1e-15)
    assert exact.reconstruct() == pytest.approx(metrics.brier(preds, labels), abs=1e-12)


def test_binned_decomposition_reconstructs_the_bin_mean_forecast(card, parts):
    """The ten bin version makes a claim about the binned forecast, so check that one."""
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    binned = metrics.murphy(preds, labels, bins=10)
    means = [0.0] * len(preds)
    for idx in metrics.equal_width_bins(preds, 10):
        if not idx:
            continue
        mean = sum(preds[i] for i in idx) / len(idx)
        for i in idx:
            means[i] = mean
    assert binned.within_bin > 0.0
    assert binned.reconstruct() == pytest.approx(metrics.brier(means, labels), abs=1e-12)


def test_murphy_terms_are_non_negative(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    dec = metrics.murphy(preds, labels)
    assert dec.reliability >= 0.0
    assert dec.resolution >= 0.0
    assert dec.uncertainty == pytest.approx(
        (sum(labels) / len(labels)) * (1 - sum(labels) / len(labels))
    )


def test_ece_is_zero_when_each_bin_is_honest():
    preds = [0.2] * 200 + [0.7] * 100
    labels = [1] * 40 + [0] * 160 + [1] * 70 + [0] * 30
    assert metrics.ece(preds, labels, bins=10) == pytest.approx(0.0, abs=1e-12)


def test_ece_rises_when_a_forecast_is_sharpened(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    honest = metrics.ece(preds, labels, bins=10)
    sharp = metrics.ece([temper(p, 2.1) for p in preds], labels, bins=10)
    assert sharp > honest * 1.1


def test_reliability_table_counts_cover_the_book(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    table = metrics.reliability_table(preds, labels, bins=10)
    assert sum(row["count"] for row in table) == len(preds)
    for row in table:
        assert 0.0 <= row["observed_rate"] <= 1.0
        assert row["lower"] <= row["upper"]


def test_log_loss_matches_hand_value():
    assert metrics.log_loss([0.5, 0.5], [1, 0]) == pytest.approx(math.log(2))
    tiny = metrics.log_loss([0.0], [1])
    assert tiny > 20.0
