"""Platt scaling: two parameters, fitted on settled loans, in logit space.

This is the smallest recalibration that deserves the name. It cannot fix a model
that ranks badly, and it cannot fix a model that is wrong in the wrong direction
for part of the book. It can fix a model that is uniformly over or under confident,
which is exactly what a prompt with a personality produces.

Newton's method is used with a backtracking line search. Plain Newton diverges on
a sharply tempered score: at the first iterate every prediction is near zero, the
curvature is tiny, and the step to the intercept is in the thousands, which parks
the fit on a saturated corner.
"""

from __future__ import annotations

import math

from .book import logit, sigmoid
from .models import _solve


def _negative_log_likelihood(x: list[float], labels: list[int], a: float, b: float) -> float:
    total = 0.0
    for xi, y in zip(x, labels):
        z = a * xi + b
        # softplus(z) - y * z, stable for both signs
        total += (z if z > 0 else 0.0) + math.log1p(math.exp(-abs(z))) - y * z
    return total


def fit_platt(preds: list[float], labels: list[int], l2: float = 1e-6,
              iterations: int = 60, tol: float = 1e-11) -> tuple[float, float]:
    """Fit sigmoid(a * logit(p) + b) by damped Newton. Returns (a, b)."""
    x = [logit(p) for p in preds]
    base = (sum(labels) + 1.0) / (len(labels) + 2.0)
    mean_x = sum(x) / len(x)
    a, b = 1.0, logit(base) - mean_x
    nll = _negative_log_likelihood(x, labels, a, b)

    for _ in range(iterations):
        g_a = -l2 * a
        g_b = 0.0
        h_aa = l2
        h_ab = 0.0
        h_bb = 0.0
        for xi, y in zip(x, labels):
            p = sigmoid(a * xi + b)
            resid = y - p
            w = p * (1.0 - p)
            g_a += resid * xi
            g_b += resid
            h_aa += w * xi * xi
            h_ab += w * xi
            h_bb += w
        try:
            step_a, step_b = _solve([[h_aa, h_ab], [h_ab, h_bb]], [g_a, g_b])
        except ValueError:
            break
        if not math.isfinite(step_a) or not math.isfinite(step_b):
            break

        # Backtrack until the likelihood improves. A step that does not improve
        # it means the quadratic model is lying, so shrink instead of trusting it.
        scale = 1.0
        improved = False
        for _ in range(40):
            cand_a, cand_b = a + scale * step_a, b + scale * step_b
            cand_nll = _negative_log_likelihood(x, labels, cand_a, cand_b)
            if cand_nll <= nll + 1e-12:
                a, b, nll = cand_a, cand_b, cand_nll
                improved = True
                break
            scale *= 0.5
        if not improved:
            break
        if max(abs(scale * step_a), abs(scale * step_b)) < tol:
            break
    return a, b


def apply_platt(preds: list[float], a: float, b: float) -> list[float]:
    return [sigmoid(a * logit(p) + b) for p in preds]


def calibration_slope(preds: list[float], labels: list[int]) -> float:
    """Slope of the recalibration map. 1.0 is honest, below 1 is overconfident."""
    a, _ = fit_platt(preds, labels)
    return a
