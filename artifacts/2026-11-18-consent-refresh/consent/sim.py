"""The simulator.

One book, one policy, 360 days. Each day: customers churn, pending re-authorisations
land, the policy decides who to prompt, then the scheduled debits are attempted.

Nothing here reads the clock. Same seed, same policy, same table.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from consent.book import (
    HORIZON_DAYS,
    LIFETIME_DAYS,
    MONTH_DAYS,
    PAY_HOUR,
    PROMPT_HOUR,
    Payer,
)
from consent.policy import Policy, View, at_risk_payment, is_contextual

# A prompt that lands next to a scheduled debit converts better: the customer is
# already dealing with that payment. A prompt after a failed debit converts worse.
CONTEXT_MULTIPLIER = 0.45
FAILURE_MULTIPLIER = 1.6
MAX_ABANDON = 1.0


@dataclass
class PayerState:
    payer: Payer
    expiry_h: float
    status: str = "active"  # active | churned | abandoned
    pending: tuple[int, float, bool, bool] | None = None
    last_prompt_day: int = field(default=-999)
    observed_max_h: float = 0.0
    failed_since_prompt: bool = False
    prompts: int = 0
    contextual_prompts: int = 0
    renewals: int = 0
    abandons: int = 0
    settles: int = 0
    refusals: int = 0
    attempts: int = 0
    captured_cents: int = 0
    refused_cents: int = 0
    settle_log: list[tuple[int, float]] = field(default_factory=list)
    exit_day: int | None = None

    def view(self, day: int) -> View:
        return View(
            pid=self.payer.pid,
            day=day,
            expiry_h=self.expiry_h,
            status=self.status,
            due_days=self.payer.due_days,
            last_prompt_day=self.last_prompt_day,
            observed_max_latency_h=self.observed_max_h,
            failed_since_prompt=self.failed_since_prompt,
            consent_start=self.payer.consent_start,
        )


@dataclass
class SimResult:
    policy: str
    states: dict[str, PayerState]
    events: list[dict]
    horizon: int

    @property
    def totals(self) -> dict:
        states = self.states.values()
        captured = sum(s.captured_cents for s in states)
        return {
            "attempts": sum(s.attempts for s in states),
            "settled": sum(s.settles for s in states),
            "refused": sum(s.refusals for s in states),
            "refused_usd": round(sum(s.refused_cents for s in states) / 100, 2),
            "captured_usd": round(captured / 100, 2),
            "prompts": sum(s.prompts for s in states),
            "contextual_prompts": sum(s.contextual_prompts for s in states),
            "renewals": sum(s.renewals for s in states),
            "abandons": sum(s.abandons for s in states),
            "churned": sum(1 for s in states if s.status == "churned"),
            "payers": len(self.states),
        }


def run(
    payers: list[Payer],
    policy: Policy,
    seed: int = 20261118,
    horizon: int = HORIZON_DAYS,
    lifetime_days: int = LIFETIME_DAYS,
    latency_scale: float = 1.0,
    context_multiplier: float = CONTEXT_MULTIPLIER,
    record_events: bool = True,
) -> SimResult:
    rng = random.Random(seed)
    states: dict[str, PayerState] = {}
    for payer in payers:
        start_h = payer.consent_start * 24 + 12
        states[payer.pid] = PayerState(payer=payer, expiry_h=start_h + lifetime_days * 24)

    events: list[dict] = []

    def log(day: int, pid: str, kind: str, **extra) -> None:
        if not record_events:
            return
        entry = {"day": day, "pid": pid, "kind": kind}
        entry.update(extra)
        events.append(entry)

    for day in range(horizon):
        cut = day * 24 + PAY_HOUR
        month_turn = day > 0 and day % MONTH_DAYS == 0

        # 1. Customers leave on their own, at the month boundary.
        if month_turn:
            for state in states.values():
                if state.status == "active" and rng.random() < state.payer.churn_hazard:
                    state.status = "churned"
                    state.exit_day = day
                    log(day, state.payer.pid, "churn")

        # 2. Re-authorisations that completed before today's payment cut.
        for state in states.values():
            if state.pending is None:
                continue
            issued, response_at, will_abandon, contextual = state.pending
            if response_at > cut:
                continue
            state.pending = None
            if will_abandon:
                state.status = "abandoned"
                state.abandons += 1
                state.exit_day = day
                log(day, state.payer.pid, "abandon", contextual=contextual)
            else:
                state.expiry_h = response_at + lifetime_days * 24
                state.renewals += 1
                latency = response_at - (issued * 24 + PROMPT_HOUR)
                state.observed_max_h = max(state.observed_max_h, latency)
                log(day, state.payer.pid, "renew", expiry_h=round(state.expiry_h, 2))

        # 3. The policy decides who to ask today.
        for state in states.values():
            if state.pending is not None or state.status != "active":
                continue
            view = state.view(day)
            if not policy.should_prompt(view):
                continue
            contextual = is_contextual(day, state.payer.due_days)
            probability = state.payer.abandon_prob
            if contextual:
                probability *= context_multiplier
            if state.failed_since_prompt:
                probability *= FAILURE_MULTIPLIER
            latency = (
                state.payer.latency_median_h
                * latency_scale
                * math.exp(rng.gauss(0.0, 0.5))
            )
            state.pending = (
                day,
                day * 24 + PROMPT_HOUR + latency,
                rng.random() < min(MAX_ABANDON, probability),
                contextual,
            )
            state.last_prompt_day = day
            state.failed_since_prompt = False
            state.prompts += 1
            if contextual:
                state.contextual_prompts += 1
            at_risk = at_risk_payment(view, horizon)
            log(day, state.payer.pid, "prompt", contextual=contextual, at_risk_day=at_risk)

        # 4. Scheduled debits.
        for state in states.values():
            if day not in state.payer.due_days or state.status != "active":
                continue
            state.attempts += 1
            if state.expiry_h > cut:
                state.settles += 1
                state.captured_cents += state.payer.bill_cents
                state.settle_log.append((day, round(state.expiry_h, 2)))
            else:
                state.refusals += 1
                state.refused_cents += state.payer.bill_cents
                state.failed_since_prompt = True

    return SimResult(policy=policy.name, states=states, events=events, horizon=horizon)


def audit_consents(result: SimResult, lifetime_days: int = LIFETIME_DAYS) -> dict:
    """Rebuild every consent timeline from the event log and check every settlement.

    Independent of the loop above: expiries come only from the logged renewals and the
    book, never from the state objects that produced the settlement.
    """
    created = {pid: s.payer.consent_start * 24 + 12 + lifetime_days * 24 for pid, s in result.states.items()}
    renewals: dict[str, list[tuple[float, float]]] = {pid: [] for pid in result.states}
    for event in result.events:
        if event["kind"] == "renew":
            renewals[event["pid"]].append((event["day"] * 24 + PAY_HOUR, event["expiry_h"]))

    violations: list[str] = []
    checked = 0
    for pid, state in result.states.items():
        for day, recorded in state.settle_log:
            at = day * 24 + PAY_HOUR
            in_force = created[pid]
            for when, expiry in sorted(renewals[pid]):
                if when <= at:
                    in_force = expiry
            checked += 1
            if in_force <= at:
                violations.append(f"{pid} settled day {day} on consent expiring {in_force:.0f}")
            if abs(in_force - recorded) > 1.0:
                violations.append(f"{pid} day {day} expiry {recorded:.0f} does not replay to {in_force:.0f}")
    return {"checked": checked, "violations": violations}
