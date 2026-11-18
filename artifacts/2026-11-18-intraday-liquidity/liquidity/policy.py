"""Opening balance policies. Each one sees history only, never the day it sizes.

A policy returns cents. The Oracle is the exception and is labelled as such: it
reads the day it sizes and exists only to bound the cost from below.
"""

from __future__ import annotations

import math
from statistics import fmean, pstdev
from typing import Sequence

from liquidity.book import Day
from liquidity.sim import required_opening


def quantile(values: Sequence[float], q: float) -> float:
    """Nearest rank quantile. Deterministic, no interpolation, no numpy."""
    if not values:
        raise ValueError("no values")
    if not 0.0 < q <= 1.0:
        raise ValueError("q must be in (0, 1]")
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def _mean(values: Sequence[float]) -> float:
    return fmean(values) if values else 0.0


class Policy:
    name = "policy"
    note = ""

    def size(self, history: Sequence[Day]) -> int:  # pragma: no cover - interface
        raise NotImplementedError


class Zero(Policy):
    name = "zero"
    note = "hold nothing overnight, fund everything from the facility"

    def size(self, history: Sequence[Day]) -> int:
        return 0


class DailyNetMean(Policy):
    name = "daily_net"
    note = "average daily net flow over the trailing window, floored at zero"

    def __init__(self, window: int = 20) -> None:
        self.window = window

    def size(self, history: Sequence[Day]) -> int:
        recent = history[-self.window :]
        if not recent:
            return 0
        return max(0, int(_mean([d.net_cents for d in recent])))


class DailyNetP95(Policy):
    name = "daily_net_p95"
    note = "trailing mean net plus 1.645 standard deviations, the textbook buffer"

    def __init__(self, window: int = 20) -> None:
        self.window = window

    def size(self, history: Sequence[Day]) -> int:
        recent = history[-self.window :]
        if not recent:
            return 0
        nets = [float(d.net_cents) for d in recent]
        lower = _mean(nets) - 1.645 * pstdev(nets) if len(nets) > 1 else _mean(nets)
        if lower >= 0:
            return 0
        return int(round(-lower))


class GrossBatch(Policy):
    name = "gross_batch"
    note = "hold the largest single payout batch seen in the trailing window"

    def __init__(self, window: int = 20) -> None:
        self.window = window

    def size(self, history: Sequence[Day]) -> int:
        recent = history[-self.window :]
        if not recent:
            return 0
        return max(d.first_batch_cents for d in recent)


class PeakPercentile(Policy):
    """Size on the trailing distribution of the required opening balance."""

    def __init__(self, q: float, window: int = 40) -> None:
        self.q = q
        self.window = window

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"peak_p{int(round(self.q * 100))}"

    note = "quantile of the trailing required opening balance, timing included"

    def size(self, history: Sequence[Day]) -> int:
        recent = history[-self.window :]
        if not recent:
            return 0
        return int(round(quantile([required_opening(d) for d in recent], self.q)))


class Oracle(Policy):
    name = "oracle"
    note = "holds exactly the balance the day needs, a floor not a policy"

    def size_for(self, day: Day) -> int:
        return required_opening(day)

    def size(self, history: Sequence[Day]) -> int:  # pragma: no cover - unused
        raise NotImplementedError("oracle sizes the day itself, use size_for")
