"""Proper scoring rules and calibration diagnostics.

Two rules (Brier, log loss), one ranking rule (AUC), and one calibration read
(ECE plus Murphy's three way decomposition). The decomposition is implemented
exactly, with one bin per distinct forecast, and again with ten bins so the
within-bin residual is visible instead of silently dropped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def brier(preds: list[float], labels: list[int]) -> float:
    if not preds or len(preds) != len(labels):
        raise ValueError("preds and labels must be non empty and the same length")
    return sum((p - y) ** 2 for p, y in zip(preds, labels)) / len(preds)


def log_loss(preds: list[float], labels: list[int], floor: float = 1e-12) -> float:
    total = 0.0
    for p, y in zip(preds, labels):
        q = min(max(p, floor), 1.0 - floor)
        total -= y * math.log(q) + (1 - y) * math.log(1.0 - q)
    return total / len(preds)


def auc(preds: list[float], labels: list[int]) -> float:
    """Rank based AUC with average ranks for ties. Unaffected by monotone maps."""
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("AUC needs both classes present")

    order = sorted(range(len(preds)), key=lambda i: preds[i])
    ranks = [0.0] * len(preds)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and preds[order[j + 1]] == preds[order[i]]:
            j += 1
        average_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1

    rank_sum = sum(r for r, y in zip(ranks, labels) if y == 1)
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def equal_width_bins(preds: list[float], bins: int = 10) -> list[list[int]]:
    groups: list[list[int]] = [[] for _ in range(bins)]
    for i, p in enumerate(preds):
        idx = min(bins - 1, max(0, int(p * bins)))
        groups[idx].append(i)
    return groups


def ece(preds: list[float], labels: list[int], bins: int = 10) -> float:
    groups = equal_width_bins(preds, bins)
    total = 0.0
    for idx in groups:
        if not idx:
            continue
        mean_p = sum(preds[i] for i in idx) / len(idx)
        mean_y = sum(labels[i] for i in idx) / len(idx)
        total += (len(idx) / len(preds)) * abs(mean_p - mean_y)
    return total


@dataclass(frozen=True)
class Decomposition:
    reliability: float
    resolution: float
    uncertainty: float
    within_bin: float

    def reconstruct(self) -> float:
        """Uncertainty + reliability - resolution.

        Exact for the forecast it was built from. With per-value bins that is the
        raw forecast, so this equals the Brier score. With integer bins it equals
        the Brier score of the bin-mean forecast, and `within_bin` reports how far
        the raw forecasts sit from those means.
        """
        return self.uncertainty + self.reliability - self.resolution


def murphy(preds: list[float], labels: list[int], bins: int | None = None) -> Decomposition:
    """Murphy decomposition.

    bins=None groups by exact forecast value, which makes within_bin exactly zero
    and reconstruct() exactly equal to the Brier score. With integer bins it does
    not: reconstruct() is then the Brier score of the bin mean, and the distance
    from the raw forecast is reported separately instead of being folded in.
    """
    n = len(preds)
    base = sum(labels) / n
    uncertainty = base * (1.0 - base)

    if bins is None:
        groups: dict[float, list[int]] = {}
        for i, p in enumerate(preds):
            groups.setdefault(p, []).append(i)
        buckets = list(groups.values())
    else:
        buckets = equal_width_bins(preds, bins)

    reliability = 0.0
    resolution = 0.0
    within = 0.0
    for idx in buckets:
        if not idx:
            continue
        w = len(idx) / n
        mean_p = sum(preds[i] for i in idx) / len(idx)
        mean_y = sum(labels[i] for i in idx) / len(idx)
        reliability += w * (mean_p - mean_y) ** 2
        resolution += w * (mean_y - base) ** 2
        within += sum((preds[i] - mean_p) ** 2 for i in idx) / n
    return Decomposition(reliability, resolution, uncertainty, within)


def reliability_table(preds: list[float], labels: list[int], bins: int = 10) -> list[dict]:
    groups = equal_width_bins(preds, bins)
    rows = []
    for b, idx in enumerate(groups):
        if not idx:
            continue
        rows.append(
            {
                "bin": b,
                "lower": round(b / bins, 2),
                "upper": round((b + 1) / bins, 2),
                "count": len(idx),
                "mean_predicted": round(sum(preds[i] for i in idx) / len(idx), 4),
                "observed_rate": round(sum(labels[i] for i in idx) / len(idx), 4),
            }
        )
    return rows


def all_metrics(preds: list[float], labels: list[int]) -> dict:
    # Report the ten bin decomposition. Per-value bins are exact but degenerate:
    # one observation per bin makes the reliability term equal the Brier score by
    # construction, which reads as a bug. The exact identity is pinned in tests.
    dec = murphy(preds, labels, bins=10)
    return {
        "brier": round(brier(preds, labels), 5),
        "log_loss": round(log_loss(preds, labels), 5),
        "auc": round(auc(preds, labels), 5),
        "accuracy_at_half": round(
            sum(1 for p, y in zip(preds, labels) if (p >= 0.5) == bool(y)) / len(preds), 5
        ),
        "ece_10": round(ece(preds, labels, 10), 5),
        "mean_predicted": round(sum(preds) / len(preds), 5),
        "observed_rate": round(sum(labels) / len(labels), 5),
        "reliability_10": round(dec.reliability, 5),
        "resolution_10": round(dec.resolution, 5),
        "uncertainty": round(dec.uncertainty, 5),
        "brier_of_bin_mean_10": round(dec.reconstruct(), 5),
        "within_bin_10": round(dec.within_bin, 5),
    }
