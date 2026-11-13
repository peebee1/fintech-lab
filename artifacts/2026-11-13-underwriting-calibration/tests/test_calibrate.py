import math
import random

import pytest

from uwcal import metrics
from uwcal.calibrate import apply_platt, calibration_slope, fit_platt
from uwcal.models import temper

SHARPEN = 2.1


def synthetic_slice(k: float, n: int = 4000, seed: int = 11):
    """A probability that is honest by construction, then distorted by k."""
    rng = random.Random(seed)
    honest = [rng.uniform(0.01, 0.6) for _ in range(n)]
    labels = [1 if rng.random() < p else 0 for p in honest]
    return [temper(p, k) for p in honest], labels


def test_platt_recovers_the_inverse_temperature():
    preds, labels = synthetic_slice(SHARPEN)
    a, b = fit_platt(preds, labels)
    assert a == pytest.approx(1.0 / SHARPEN, abs=0.06)
    assert b == pytest.approx(0.0, abs=0.25)


def test_platt_recovers_a_flattened_score():
    preds, labels = synthetic_slice(0.55)
    a, _ = fit_platt(preds, labels)
    assert a == pytest.approx(1.0 / 0.55, abs=0.10)


def test_platt_is_not_saturated_by_a_sharp_score(card, parts):
    """Plain Newton diverged here: the first step sent the intercept to +6500000000."""
    calib = parts["calibration"]
    labels = [loan.defaulted for loan in calib]
    preds = [temper(p, SHARPEN) for p in card.predict(calib)]
    a, b = fit_platt(preds, labels)
    assert math.isfinite(a) and math.isfinite(b)
    fixed = apply_platt(preds, a, b)
    assert all(0.001 < p < 0.999 for p in fixed)


def test_recalibration_preserves_the_ranking(card, parts):
    holdout = parts["holdout"]
    labels = [loan.defaulted for loan in holdout]
    calib = parts["calibration"]
    calib_labels = [loan.defaulted for loan in calib]
    preds = card.predict(holdout)
    a, b = fit_platt(card.predict(calib), calib_labels)
    fixed = apply_platt(preds, a, b)
    assert metrics.auc(fixed, labels) == pytest.approx(metrics.auc(preds, labels), abs=1e-12)


def test_recalibration_improves_out_of_sample_brier(card, parts):
    calib, holdout = parts["calibration"], parts["holdout"]
    calib_labels = [loan.defaulted for loan in calib]
    labels = [loan.defaulted for loan in holdout]
    sharp_calib = [temper(p, SHARPEN) for p in card.predict(calib)]
    sharp_holdout = [temper(p, SHARPEN) for p in card.predict(holdout)]
    a, b = fit_platt(sharp_calib, calib_labels)
    before = metrics.brier(sharp_holdout, labels)
    after = metrics.brier(apply_platt(sharp_holdout, a, b), labels)
    assert after < before * 0.97


def test_recalibration_leaves_an_honest_model_alone(card, parts):
    calib, holdout = parts["calibration"], parts["holdout"]
    a, b = fit_platt(card.predict(calib), [loan.defaulted for loan in calib])
    labels = [loan.defaulted for loan in holdout]
    before = metrics.brier(card.predict(holdout), labels)
    after = metrics.brier(apply_platt(card.predict(holdout), a, b), labels)
    assert after == pytest.approx(before, abs=0.004)


def test_slope_separates_over_from_under_confidence(card, parts):
    calib = parts["calibration"]
    labels = [loan.defaulted for loan in calib]
    preds = card.predict(calib)
    sharp = calibration_slope([temper(p, SHARPEN) for p in preds], labels)
    flat = calibration_slope([temper(p, 0.55) for p in preds], labels)
    assert 0.25 < sharp < 0.80
    assert 1.25 < flat < 2.40
    assert sharp < 1.0 < flat


def test_platt_survives_a_degenerate_slice():
    # every loan performing: the fit must not raise or return nan
    a, b = fit_platt([0.05, 0.2, 0.6], [0, 0, 0])
    assert math.isfinite(a) and math.isfinite(b)
