"""Routing policies.

Every policy returns a full preference order, not one name, because a decline
has to be retried somewhere and the second choice is part of the policy.
"""

from __future__ import annotations

import random
from collections import deque

from . import data, psps
from .data import Txn


class Policy:
    name = "base"

    def rank(self, txn: Txn) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def observe(self, txn: Txn, psp: str, authorized: bool, reward: int) -> None:
        return None


def _by_fee(txn: Txn) -> list[str]:
    return sorted(psps.names(), key=lambda n: (psps.BY_NAME[n].fee(txn.amount), n))


class Cheapest(Policy):
    """The contract view: route to the lowest published fee for this ticket."""

    name = "cheapest"

    def rank(self, txn: Txn) -> list[str]:
        return _by_fee(txn)


class StaticRules(Policy):
    """What a payments team writes after reading three vendor decks.

    Cross-border to the specialist, debit to the debit specialist, everything
    else to the cheap one. Ticket size never enters the rule.
    """

    name = "static_rules"

    def rank(self, txn: Txn) -> list[str]:
        if txn.region == "cross_border":
            first = "charlie"
        elif txn.channel == "debit":
            first = "bravo"
        else:
            first = "alpha"
        rest = [n for n in _by_fee(txn) if n != first]
        return [first] + rest


class EpsilonGreedy(Policy):
    """One mean reward per context and provider, fixed exploration rate."""

    name = "epsilon_greedy"

    def __init__(self, epsilon: float = 0.10, seed: int = 11) -> None:
        self.epsilon = epsilon
        self.rng = random.Random(seed)
        self.total: dict[tuple[str, str], int] = {}
        self.count: dict[tuple[str, str], int] = {}

    def value(self, context: str, psp: str) -> float:
        n = self.count.get((context, psp), 0)
        return self.total.get((context, psp), 0) / n if n else 0.0

    def rank(self, txn: Txn) -> list[str]:
        context = txn.context
        unseen = [n for n in _by_fee(txn) if self.count.get((context, n), 0) == 0]
        if unseen:
            first = unseen[0]
        elif self.rng.random() < self.epsilon:
            first = self.rng.choice(list(psps.names()))
        else:
            first = max(psps.names(), key=lambda n: (self.value(context, n), -psps.BY_NAME[n].fee(txn.amount)))
        rest = sorted(
            (n for n in psps.names() if n != first),
            key=lambda n: (-self.value(context, n), psps.BY_NAME[n].fee(txn.amount), n),
        )
        return [first] + rest

    def observe(self, txn: Txn, psp: str, authorized: bool, reward: int) -> None:
        key = (txn.context, psp)
        self.total[key] = self.total.get(key, 0) + reward
        self.count[key] = self.count.get(key, 0) + 1


class _ThompsonBase(Policy):
    """Shared ranking logic: sample approval, cost the sample, take the best."""

    def __init__(self, seed: int = 13) -> None:
        self.rng = random.Random(seed)

    def params(self, context: str, psp: str) -> tuple[float, float]:  # pragma: no cover - interface
        raise NotImplementedError

    def sample_value(self, txn: Txn, psp: str) -> float:
        a, b = self.params(txn.context, psp)
        p = self.rng.betavariate(a, b)
        return p * (data.margin_cents(txn.amount) - psps.BY_NAME[psp].fee(txn.amount)) - data.OPS_CENTS

    def rank(self, txn: Txn) -> list[str]:
        return sorted(psps.names(), key=lambda n: (-self.sample_value(txn, n), n))


class Thompson(_ThompsonBase):
    """A Beta posterior on approval per context and provider, all history.

    Fees are known, approval is not, so the posterior is only over the approval
    probability. Exploration comes from sampling the posterior and costing the
    sample, not from a coin flip. The cost of keeping all history is that the
    posterior gets very sure, and a provider that changes behaviour is averaged
    away instead of noticed.
    """

    name = "thompson"

    def __init__(self, seed: int = 13) -> None:
        super().__init__(seed)
        self.posterior: dict[tuple[str, str], list[int]] = {}

    def params(self, context: str, psp: str) -> tuple[float, float]:
        a, b = self.posterior.setdefault((context, psp), [1, 1])
        return float(a), float(b)

    def observe(self, txn: Txn, psp: str, authorized: bool, reward: int) -> None:
        cell = self.posterior.setdefault((txn.context, psp), [1, 1])
        cell[0] += int(authorized)
        cell[1] += 0 if authorized else 1


class ThompsonWindow(_ThompsonBase):
    """The same sampler, with the posterior built only from the last N attempts.

    The window is the cheapest possible answer to regime change: forget old
    evidence instead of testing for a change point.
    """

    name = "thompson_window"

    def __init__(self, window: int = 300, seed: int = 17) -> None:
        super().__init__(seed)
        self.window = window
        self.history: dict[tuple[str, str], deque[int]] = {}

    def params(self, context: str, psp: str) -> tuple[float, float]:
        seen = self.history.get((context, psp))
        if not seen:
            return 1.0, 1.0
        wins = sum(seen)
        return 1.0 + wins, 1.0 + (len(seen) - wins)

    def observe(self, txn: Txn, psp: str, authorized: bool, reward: int) -> None:
        key = (txn.context, psp)
        seen = self.history.setdefault(key, deque(maxlen=self.window))
        seen.append(1 if authorized else 0)


class Oracle(Policy):
    """Full knowledge of the approval curve, ranked by expected net.

    Generated after the fact with the true model, so it is a reference line and
    not something a running system can be. It also ignores the value of the
    retry option, which makes it a floor on the true optimum.
    """

    name = "oracle"

    def __init__(self, margin_bps: int = data.MARGIN_BPS, drift: psps.Drift | None = None) -> None:
        self.margin_bps = margin_bps
        self.drift = drift

    def rank(self, txn: Txn) -> list[str]:
        return sorted(
            psps.names(),
            key=lambda n: (-psps.BY_NAME[n].expected_net(txn, self.margin_bps, self.drift), n),
        )
