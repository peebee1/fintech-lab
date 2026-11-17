"""Refresh policies.

A policy sees the consent as it stands today and answers one question: prompt now,
or wait. It does not know the customer's next answer, only what has happened so far.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from consent.book import CONTEXT_DAYS, PAY_HOUR


@dataclass(frozen=True)
class View:
    """What a policy is allowed to see. Everything here is known before the prompt."""

    pid: str
    day: int
    expiry_h: float
    status: str
    due_days: tuple[int, ...]
    last_prompt_day: int
    observed_max_latency_h: float
    failed_since_prompt: bool
    consent_start: int

    def future_due_days(self) -> tuple[int, ...]:
        return tuple(d for d in self.due_days if d >= self.day)


def at_risk(expiry_h: float, due_day: int) -> bool:
    """Would a debit on this day land on or after the consent expiry?"""
    return due_day * 24 + PAY_HOUR >= expiry_h


def at_risk_payment(view: View, horizon_days: int) -> int | None:
    """The first scheduled debit this consent cannot cover, if any."""
    for due in view.future_due_days():
        if due > view.day + horizon_days:
            return None
        if at_risk(view.expiry_h, due):
            return due
    return None


class Policy:
    name = "policy"

    def should_prompt(self, view: View) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class NeverRefresh(Policy):
    """Let the consent run to its expiry and never ask for another one."""

    name = "never_refresh"

    def should_prompt(self, view: View) -> bool:
        return False


class OnFailure(Policy):
    """Do nothing until a debit is refused, then ask."""

    name = "on_failure"

    def should_prompt(self, view: View) -> bool:
        if not view.failed_since_prompt:
            return False
        return bool(view.future_due_days())


class FixedCadence(Policy):
    """Ask on a calendar, every N days, whatever the payment schedule looks like."""

    def __init__(self, days: int) -> None:
        self.days = days
        self.name = f"fixed_{days}"

    def should_prompt(self, view: View) -> bool:
        if view.day - view.last_prompt_day < self.days:
            return False
        return bool(view.future_due_days())


class JustInTime(Policy):
    """Ask only when a scheduled debit would land after expiry, and only `lead` days out."""

    def __init__(self, lead_days: int) -> None:
        self.lead_days = lead_days
        self.name = f"jit_{lead_days}"

    def should_prompt(self, view: View) -> bool:
        for due in view.future_due_days():
            if due - view.day > self.lead_days:
                continue
            if at_risk(view.expiry_h, due):
                return True
        return False


class AdaptiveLead(JustInTime):
    """Set the lead from the customer's own re-authorisation latency, not the calendar.

    A customer who takes four days to answer needs a four day lead. One who answers in
    an hour does not, and prompting them a week early moves the prompt out of the
    contextual window next to the debit.
    """

    def __init__(self, floor: int = 2, ceiling: int = 21, default: int = 7) -> None:
        self.floor = floor
        self.ceiling = ceiling
        self.default = default
        super().__init__(lead_days=default)
        self.name = "adaptive_lead"

    def lead_for(self, view: View) -> int:
        if view.observed_max_latency_h <= 0:
            return self.default
        days = math.ceil(view.observed_max_latency_h / 24.0) + 1
        return max(self.floor, min(self.ceiling, days))

    def should_prompt(self, view: View) -> bool:
        lead = self.lead_for(view)
        for due in view.future_due_days():
            if due - view.day > lead:
                continue
            if at_risk(view.expiry_h, due):
                return True
        return False


def is_contextual(day: int, due_days: tuple[int, ...]) -> bool:
    """Is the prompt close enough to a debit to count as part of that payment flow?"""
    return any(0 <= due - day <= CONTEXT_DAYS for due in due_days)
