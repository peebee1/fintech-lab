import math
import random

import pytest

from uwcal import book, metrics
from uwcal.models import Scorecard, fit_logistic, temper


def test_logistic_recovers_a_known_slope():
    rng = random.Random(5)
    xs = [rng.uniform(-2.5, 2.5) for _ in range(4000)]
    labels = [1 if rng.random() < book.sigmoid(1.2 * (x - 0.3)) else 0 for x in xs]
    beta = fit_logistic([[1.0, x] for x in xs], labels, l2=0.01)
    assert beta[1] == pytest.approx(1.2, abs=0.25)
    assert beta[0] == pytest.approx(-0.36, abs=0.30)


def test_scorecard_coefficients_are_named_and_finite(card):
    coefs = card.coefficients()
    assert set(coefs) == {"intercept", *book.FEATURES}
    assert all(math.isfinite(v) for v in coefs.values())


def test_scorecard_predictions_are_probabilities(card, parts):
    preds = card.predict(parts["holdout"])
    assert len(preds) == len(parts["holdout"])
    assert all(0.0 < p < 1.0 for p in preds)


def test_scorecard_is_deterministic(card, parts):
    assert card.predict(parts["holdout"]) == card.predict(parts["holdout"])


def test_more_leverage_scores_worse(card):
    base = book.Loan(0, 0.25, 0.30, 0.70, 70.0, 0, 60, 5000.0, 0, 0.0)
    tight = book.Loan(1, 0.70, 1.20, 1.05, 22.0, 4, 2, 5000.0, 0, 0.0)
    p_base = card.predict([base])[0]
    p_tight = card.predict([tight])[0]
    assert p_tight > p_base * 2


def test_scorecard_ranks_with_the_true_probability(card, parts):
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    deciles = sorted(range(len(holdout)), key=lambda i: holdout[i].true_pd)
    low = sum(preds[i] for i in deciles[: len(deciles) // 5]) / (len(deciles) // 5)
    high = sum(preds[i] for i in deciles[-len(deciles) // 5:]) / (len(deciles) // 5)
    assert high > low * 2


def test_fit_requires_coefficients():
    with pytest.raises(ValueError):
        Scorecard().predict([])


def test_temper_is_monotone_and_bends_toward_extremes():
    assert temper(0.5, 2.1) == pytest.approx(0.5)
    assert temper(0.2, 2.1) < 0.2
    assert temper(0.2, 0.55) > 0.2
    values = [temper(p / 100, 2.1) for p in range(1, 100)]
    assert values == sorted(values)


def test_temper_changes_brier_but_not_auc(card, parts):
    preds = card.predict(parts["holdout"])
    labels = [loan.defaulted for loan in parts["holdout"]]
    sharp = [temper(p, 2.1) for p in preds]
    assert metrics.auc(sharp, labels) == pytest.approx(metrics.auc(preds, labels), abs=1e-12)
    assert metrics.brier(sharp, labels) > metrics.brier(preds, labels)
