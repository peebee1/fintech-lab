"""Four policies over one book, stepped one day at a time.

The ladder is additive, so each step isolates one decision:

    status_only    no clock, fixed three week sweep, submit whatever arrived
    response_clock one deadline per network and reason code, queue by deadline
    frees_added    plus the zero evidence wins: procedural and liability
    three_clock    plus evidence sufficiency, value per minute, and pre arbitration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import rules
from .model import ALLOWED, TERMINAL, WON_STATES, Book, Case, State


@dataclass
class CaseState:
    case: Case
    deadline: date
    state: State = State.OPEN
    submitted: tuple[str, ...] = ()
    minutes: int = 0
    pushback_day: date | None = None
    pre_arb_deadline: date | None = None
    pre_arb_answered: bool = False
    trace: list[State] = field(default_factory=list)

    def move(self, state: State) -> None:
        if state not in ALLOWED.get(self.state, frozenset()):
            raise ValueError(
                f"{self.case.id}: illegal transition {self.state.value} -> {state.value}"
            )
        self.trace.append(state)
        self.state = state


def _expire(st: CaseState) -> None:
    st.move(State.FORFEITED if st.case.defensible else State.ACCEPTED)


class Policy:
    name = "policy"

    def plan(self, states: list[CaseState], day: date) -> list[tuple[str, str, tuple[str, ...]]]:
        raise NotImplementedError


class StatusOnly(Policy):
    """A status tracker: works every dispute on the same three week habit."""

    name = "status_only"
    sweep_days = 25

    def plan(self, states, day):
        out = []
        for st in sorted(states, key=lambda s: (s.case.arrival, s.case.id)):
            if st.state is State.OPEN and (day - st.case.arrival).days >= self.sweep_days:
                out.append((st.case.id, "contest", rules.available_on(st.case, day)))
        return out


class ResponseClock(Policy):
    """One clock, modelled properly: the real deadline, worked oldest first."""

    name = "response_clock"
    lead_days = 7

    def wants(self, st: CaseState, day: date) -> bool:
        return (st.deadline - day).days <= self.lead_days

    def evidence(self, st: CaseState, day: date) -> tuple[str, ...]:
        """What this policy submits. By default, everything that has landed."""
        return rules.available_on(st.case, day)

    def contest_queue(self, states, day):
        todo = [s for s in states if s.state is State.OPEN and self.wants(s, day)]
        return [
            (st.case.id, "contest", self.evidence(st, day))
            for st in sorted(todo, key=lambda s: (s.deadline, s.case.id))
        ]

    def plan(self, states, day):
        return self.contest_queue(states, day)


class FreesAdded(ResponseClock):
    """Adds the cases that need no evidence at all."""

    name = "frees_added"

    def free_queue(self, states) -> tuple[list, set[str]]:
        out = []
        free_ids: set[str] = set()
        for st in sorted(states, key=lambda s: (s.case.arrival, s.case.id)):
            if st.state is State.OPEN and st.case.free_win:
                out.append((st.case.id, "auto", ()))
                free_ids.add(st.case.id)
        return out, free_ids

    def plan(self, states, day):
        out, free_ids = self.free_queue(states)
        out.extend(self.contest_queue([s for s in states if s.case.id not in free_ids], day))
        return out


class CompleteEvidence(FreesAdded):
    """Adds the evidence gate: never submit a set that cannot win."""

    name = "complete_evidence"

    def wants(self, st: CaseState, day: date) -> bool:
        if not super().wants(st, day):
            return False
        return set(st.case.required) <= set(rules.available_on(st.case, day))

    def evidence(self, st: CaseState, day: date) -> tuple[str, ...]:
        return st.case.required


class ThreeClock(FreesAdded):
    """All three clocks, the evidence gate, and a value per minute queue."""

    name = "three_clock"
    urgent_days = 3
    pushback_prior = 0.55

    def plan(self, states, day):
        out, free_ids = self.free_queue(states)

        ready = [
            s
            for s in states
            if s.state is State.OPEN
            and s.case.id not in free_ids
            and set(s.case.required) <= set(rules.available_on(s.case, day))
        ]
        ranked: list[tuple[tuple, str, tuple[str, ...]]] = []
        for st in ready:
            remaining = (st.deadline - day).days
            key = (
                0 if remaining <= self.urgent_days else 1,
                -self.ev_per_minute(st),
                remaining,
                st.case.id,
            )
            ranked.append((key, "contest", st.case.required))

        for st in states:
            if st.state is not State.PRE_ARB_DUE or st.pre_arb_deadline is None:
                continue
            remaining = (st.pre_arb_deadline - day).days
            ev = st.case.amount_minor * self.pushback_prior / rules.PRE_ARB_MINUTES
            key = (0 if remaining <= self.urgent_days else 1, -ev, remaining, st.case.id)
            ranked.append((key, "pre_arb", ()))

        ranked.sort(key=lambda item: item[0])
        out.extend((key[3], action, evidence) for key, action, evidence in ranked)
        return out

    @staticmethod
    def ev_per_minute(st: CaseState) -> float:
        return st.case.amount_minor / max(1, rules.evidence_minutes(st.case.required))


@dataclass
class RunResult:
    policy: str
    states: list[CaseState]
    minutes: int
    skipped: int
    days: int

    @property
    def recovered_minor(self) -> int:
        return sum(s.case.amount_minor for s in self.states if s.state in WON_STATES)

    @property
    def lost_minor(self) -> int:
        return sum(s.case.amount_minor for s in self.states if s.state not in WON_STATES)

    def stats(self) -> dict:
        won = [s for s in self.states if s.state in WON_STATES]
        recoverable = sum(s.case.amount_minor for s in self.states if s.case.defensible)
        contested = [s for s in self.states if State.SUBMITTED in s.trace]
        contested_won = [s for s in contested if s.state in WON_STATES]
        free = [s for s in self.states if s.case.free_win]
        free_won = [s for s in free if s.state in WON_STATES]
        forfeited = [s for s in self.states if s.state is State.FORFEITED]
        accepted = [s for s in self.states if s.state is State.ACCEPTED]
        lost = [s for s in self.states if s.state in (State.LOST, State.PRE_ARB_LOST)]
        pre_arb = [s for s in self.states if State.PRE_ARB_DUE in s.trace]
        pre_arb_lost = [s for s in pre_arb if s.state is not State.WON]
        recovered = self.recovered_minor

        def usd(minor: int) -> float:
            return round(minor / 100, 2)

        return {
            "policy": self.policy,
            "recovered_usd": usd(recovered),
            "recoverable_usd": usd(recoverable),
            "recovery_rate": round(recovered / recoverable, 4) if recoverable else 0.0,
            "forfeited_cases": len(forfeited),
            "forfeited_usd": usd(sum(s.case.amount_minor for s in forfeited)),
            "forfeited_fraud_cases": sum(1 for s in forfeited if s.case.reason.is_fraud),
            "forfeited_service_cases": sum(1 for s in forfeited if not s.case.reason.is_fraud),
            "accepted_cases": len(accepted),
            "accepted_usd": usd(sum(s.case.amount_minor for s in accepted)),
            "lost_contest_cases": len(lost),
            "lost_usd": usd(self.lost_minor),
            "contested": len(contested),
            "contest_precision": round(len(contested_won) / len(contested), 4) if contested else 0.0,
            "free_win_cases": len(free),
            "free_win_captured_cases": len(free_won),
            "free_win_usd": usd(sum(s.case.amount_minor for s in free)),
            "free_win_captured_usd": usd(sum(s.case.amount_minor for s in free_won)),
            "pre_arb_cases": len(pre_arb),
            "pre_arb_answered": sum(1 for s in pre_arb if s.pre_arb_answered),
            "pre_arb_won_usd": usd(
                sum(
                    s.case.amount_minor
                    for s in pre_arb
                    if s.pre_arb_answered and s.state is State.WON
                )
            ),
            "pre_arb_lost_cases": len(pre_arb_lost),
            "pre_arb_lost_usd": usd(sum(s.case.amount_minor for s in pre_arb_lost)),
            "minutes": self.minutes,
            "minutes_per_day": round(self.minutes / self.days, 1),
            "wasted_minutes": sum(s.minutes for s in self.states if s.state not in WON_STATES),
            "skipped_for_budget": self.skipped,
        }


def run(book: Book, policy: Policy, budget_per_day: int = 120) -> RunResult:
    days = [book.start + timedelta(days=i) for i in range(book.horizon + 1)]
    arrivals = book.by_arrival
    active: dict[str, CaseState] = {}
    finished: list[CaseState] = []
    minutes = 0
    skipped = 0

    for day in days:
        for case in arrivals.get(day, ()):
            active[case.id] = CaseState(case=case, deadline=rules.response_deadline(case))

        for st in active.values():
            if st.state is State.WON and st.pushback_day == day:
                st.move(State.PRE_ARB_DUE)

        budget = budget_per_day
        pending = [s for s in active.values() if s.state in (State.OPEN, State.PRE_ARB_DUE)]
        for case_id, action, evidence in policy.plan(pending, day):
            st = active[case_id]
            cost = rules.PRE_ARB_MINUTES if action == "pre_arb" else rules.evidence_minutes(evidence)
            if cost > budget:
                skipped += 1
                continue
            budget -= cost
            minutes += cost
            st.minutes += cost
            _apply(st, action, evidence, day)

        for case_id, st in list(active.items()):
            if st.state is State.OPEN and day > st.deadline:
                _expire(st)
            elif (
                st.state is State.PRE_ARB_DUE
                and st.pre_arb_deadline is not None
                and day > st.pre_arb_deadline
            ):
                st.move(State.PRE_ARB_LOST)
            waiting = st.state is State.WON and st.pushback_day is not None and st.pushback_day > day
            if st.state in TERMINAL and not waiting:
                finished.append(active.pop(case_id))

    return RunResult(
        policy=policy.name,
        states=finished + list(active.values()),
        minutes=minutes,
        skipped=skipped,
        days=len(days),
    )


def _apply(st: CaseState, action: str, evidence: tuple[str, ...], day: date) -> None:
    if action == "auto":
        st.move(State.AUTO_WON)
        return
    if action == "contest":
        if day > st.deadline:
            _expire(st)
            return
        st.submitted = tuple(evidence)
        st.move(State.SUBMITTED)
        if set(st.case.required) <= set(evidence):
            st.move(State.WON)
            if st.case.pre_arb:
                st.pushback_day = rules.payment_received(day)
                st.pre_arb_deadline = rules.pre_arb_deadline(st.pushback_day, st.case)
        else:
            st.move(State.LOST)
        return
    if action == "pre_arb":
        st.pre_arb_answered = True
        st.pushback_day = None
        st.move(State.WON if st.case.pre_arb_wins else State.PRE_ARB_LOST)
        return
    raise ValueError(f"unknown action: {action}")
