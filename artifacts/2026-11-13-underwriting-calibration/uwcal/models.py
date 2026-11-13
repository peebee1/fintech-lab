"""A scorecard fitted by hand, plus the two ways a probability goes wrong.

The point of the bench is not this scorecard. It is that a model can rank exactly
the same loans in exactly the same order and still report probabilities that are
half or double the truth. Both variants below use the same fitted score and change
only the map from score to probability, so their AUC is identical to the baseline
by construction, and a ranking metric cannot see the difference.
"""

from __future__ import annotations

import math

from .book import FEATURES, Loan, logit, sigmoid


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular normal equations")
        a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        a[col] = [v / div for v in a[col]]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            if factor == 0.0:
                continue
            a[r] = [vr - factor * vc for vr, vc in zip(a[r], a[col])]
    return [a[i][n] for i in range(n)]


def fit_logistic(rows: list[list[float]], labels: list[int], l2: float = 1.0,
                 iterations: int = 40, tol: float = 1e-10) -> list[float]:
    """Newton-Raphson (IRLS) with a ridge penalty on everything but the intercept."""
    d = len(rows[0])
    beta = [0.0] * d
    for _ in range(iterations):
        grad = [0.0] * d
        hess = [[0.0] * d for _ in range(d)]
        for row, y in zip(rows, labels):
            p = sigmoid(sum(b * x for b, x in zip(beta, row)))
            w = p * (1.0 - p)
            for i in range(d):
                grad[i] += (y - p) * row[i]
                wr = w * row[i]
                for j in range(d):
                    hess[i][j] += wr * row[j]
        for i in range(1, d):
            grad[i] -= l2 * beta[i]
            hess[i][i] += l2
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < tol:
            break
    return beta


def temper(p: float, k: float) -> float:
    """Stretch or flatten a probability in logit space. k > 1 is overconfidence."""
    return sigmoid(k * logit(p))


class Scorecard:
    """Standardize, fit, predict. Deterministic and order independent."""

    def __init__(self, l2: float = 1.0) -> None:
        self.l2 = l2
        self.means: list[float] = []
        self.stds: list[float] = []
        self.beta: list[float] = []

    def _standardize(self, loans: list[Loan]) -> list[list[float]]:
        rows = []
        for loan in loans:
            raw = loan.features()
            scaled = [
                (value - mean) / std for value, mean, std in zip(raw, self.means, self.stds)
            ]
            rows.append([1.0] + scaled)
        return rows

    def fit(self, loans: list[Loan]) -> "Scorecard":
        columns = list(zip(*[loan.features() for loan in loans]))
        self.means = [sum(col) / len(col) for col in columns]
        self.stds = []
        for col, mean in zip(columns, self.means):
            var = sum((v - mean) ** 2 for v in col) / len(col)
            self.stds.append(math.sqrt(var) or 1.0)
        rows = []
        for loan in loans:
            scaled = [
                (v - m) / s for v, m, s in zip(loan.features(), self.means, self.stds)
            ]
            rows.append([1.0] + scaled)
        self.beta = fit_logistic(rows, [loan.defaulted for loan in loans], l2=self.l2)
        return self

    def predict(self, loans: list[Loan]) -> list[float]:
        if not self.beta:
            raise ValueError("scorecard is not fitted")
        return [sigmoid(sum(b * x for b, x in zip(self.beta, row)))
                for row in self._standardize(loans)]

    def coefficients(self) -> dict[str, float]:
        names = ["intercept", *FEATURES]
        return {name: round(b, 4) for name, b in zip(names, self.beta)}
