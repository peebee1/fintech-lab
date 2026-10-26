"""Population generator and the presentation engine.

A scheduler is a pure function of (invoice, rail spec, attempt index); the rail
decides what happens to that presentation. Nothing here reads a clock.

Two behaviours are noise, not rules, and both come from the seed: whether the
payer is short of funds that day, and whether the payer bothers to exercise a
refund right they hold. A right is not a refund. Treating them as the same thing
would turn an exposure into a certain loss and flatter any planner that avoids it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import rails
from .model import (
    CLEAN,
    DECLINED,
    DECLINED_AFA,
    DECLINED_FUNDS,
    DECLINED_REVOKED,
    DECLINED_TOO_SOON,
    EXPOSED,
    NOT_PRESENTED,
    REVERSED,
    SETTLED,
    Attempt,
    Invoice,
    Population,
    Resolution,
    RunResult,
    Subscriber,
)

RAIL_MIX = (("card", 50), ("sepa", 30), ("upi", 20))

EUR_TIERS = (999, 1499, 1999, 2499, 2900, 4900, 9900, 14900, 19900)
INR_TIERS = (49900, 99000, 149900, 199900, 249900, 499900)
INR_OVER_CAP_TIERS = (1_500_100, 1_899_900, 2_499_900)

# Share of payers who act on a refund right they hold. A debit taken without the
# required notice is often never noticed at all. A debit taken after the payer
# actively cancelled is usually disputed.
CLAIM_NOTICE = 0.35
CLAIM_REVOCATION = 0.80

SHORT_DAY_SHARE = 0.07
REVOKE_SHARE = 0.08
SAME_DAY_SHARE = 0.25
AFA_APPROVAL = 0.70
AFA_RETRY_APPROVAL = 0.20
OVER_CAP_SHARE = 0.03


@dataclass(frozen=True)
class Planner:
    """A scheduling policy. The flags are the whole difference between the three."""

    id: str
    label: str
    honours_notice: bool
    stops_on_revocation: bool
    requests_afa: bool

    def schedule_day(self, invoice: Invoice, spec: rails.RailSpec, index: int) -> int:
        """Day of the index-th presentation this planner will attempt."""
        if self.honours_notice:
            base = spec.first_day(invoice.due_day, invoice.issued_day)
            step = spec.retry_gap_days + spec.retry_lead()
        else:
            base = invoice.due_day
            step = 1
        return base + index * step

    def notice_day(self, attempt_day: int, spec: rails.RailSpec) -> int:
        """Day the payer was told about this debit. A planner that skips notice tells nobody."""
        return attempt_day - spec.prenotify_days if self.honours_notice else attempt_day


PLANNERS: dict[str, Planner] = {
    "naive": Planner(
        id="naive",
        label="Naive: due date, daily retries, no notice, no cap check",
        honours_notice=False,
        stops_on_revocation=False,
        requests_afa=False,
    ),
    "notice_aware": Planner(
        id="notice_aware",
        label="Notice and cap aware, revocation blind",
        honours_notice=True,
        stops_on_revocation=False,
        requests_afa=True,
    ),
    "rail_aware": Planner(
        id="rail_aware",
        label="Rail aware: notice, cap, retry gap, and revocation",
        honours_notice=True,
        stops_on_revocation=True,
        requests_afa=True,
    ),
}


def build_population(
    seed: int = 7,
    subscribers: int = 2000,
    horizon_days: int = 180,
    cycles: int = 6,
) -> Population:
    """Synthetic book. Every subscriber, gap, and authentication result comes from the seed."""
    rng = random.Random(seed)
    rail_ids = [rail for rail, _ in RAIL_MIX]
    weights = [weight for _, weight in RAIL_MIX]

    subs: list[Subscriber] = []
    short_days: dict[str, frozenset[int]] = {}
    for index in range(subscribers):
        rail = rng.choices(rail_ids, weights=weights, k=1)[0]
        if rail == "upi":
            amount = (
                rng.choice(INR_OVER_CAP_TIERS)
                if rng.random() < OVER_CAP_SHARE
                else rng.choice(INR_TIERS)
            )
        else:
            amount = rng.choice(EUR_TIERS)
        revoke = rng.randint(20, horizon_days - 10) if rng.random() < REVOKE_SHARE else None
        sub = Subscriber(
            id=f"S{index:05d}",
            rail=rail,
            amount_minor=amount,
            due_day=rng.randint(1, 28),
            revoke_request_day=revoke,
        )
        subs.append(sub)
        count = max(1, int((horizon_days + 1) * SHORT_DAY_SHARE))
        short_days[sub.id] = frozenset(rng.sample(range(horizon_days + 1), k=count))

    invoices: list[Invoice] = []
    afa_approved: dict[tuple[str, int], bool] = {}
    claim_draw: dict[str, float] = {}
    for sub in subs:
        for cycle in range(cycles):
            due = sub.due_day + 30 * cycle
            if due > horizon_days:
                break
            issued = due if rng.random() < SAME_DAY_SHARE else max(0, due - 20)
            # A cancelled subscriber stops being billed from the day they cancel.
            if sub.revoke_request_day is not None and issued > sub.revoke_request_day:
                continue
            invoice = Invoice(
                id=f"{sub.id}-{cycle}",
                subscriber_id=sub.id,
                rail=sub.rail,
                amount_minor=sub.amount_minor,
                issued_day=issued,
                due_day=due,
                cycle=cycle,
            )
            invoices.append(invoice)
            # The payer is prompted once per presentation. A payer who ignored the
            # first prompt is much less likely to approve a later one.
            afa_approved[(invoice.id, 0)] = rng.random() < AFA_APPROVAL
            for retry in range(1, 4):
                afa_approved[(invoice.id, retry)] = rng.random() < AFA_RETRY_APPROVAL
            claim_draw[invoice.id] = rng.random()

    return Population(
        subscribers=tuple(subs),
        invoices=tuple(invoices),
        short_days=short_days,
        afa_approved=afa_approved,
        claim_draw=claim_draw,
        horizon_days=horizon_days,
        seed=seed,
    )


def present(
    invoice: Invoice,
    subscriber: Subscriber,
    spec: rails.RailSpec,
    planner: Planner,
    attempt_day: int,
    previous_day: int | None,
    population: Population,
    index: int = 0,
) -> Attempt:
    """What the rail does with one presentation."""
    effective = subscriber.revoke_effective_day(spec.revoke_lag_days)
    notice_day = planner.notice_day(attempt_day, spec)
    reasons = rails.violation_reasons(
        spec, attempt_day, notice_day, subscriber.revoke_request_day, effective
    )

    if effective is not None and attempt_day >= effective:
        outcome = DECLINED_REVOKED
    elif spec.needs_afa(invoice.amount_minor):
        approved = population.afa_approved.get((invoice.id, index), False)
        outcome = SETTLED if (planner.requests_afa and approved) else DECLINED_AFA
    elif previous_day is not None and attempt_day - previous_day < spec.retry_gap_days:
        outcome = DECLINED_TOO_SOON
    elif attempt_day in population.short_days.get(subscriber.id, frozenset()):
        outcome = DECLINED_FUNDS
    else:
        outcome = SETTLED

    return Attempt(
        invoice_id=invoice.id,
        rail=invoice.rail,
        day=attempt_day,
        amount_minor=invoice.amount_minor,
        index=index,
        notice_day=notice_day,
        outcome=outcome,
        reasons=reasons if outcome == SETTLED else (),
    )


def resolve(invoice: Invoice, attempts: list[Attempt], claim_draw: float) -> Resolution:
    """Collapse one invoice's presentations into exactly one state.

    The amount is counted once, in one bucket. Attempt level totals can then be
    checked against invoice level totals, and they have to agree.
    """
    settled = [a for a in attempts if a.settled]
    if settled:
        first = settled[0]
        if first.reasons:
            threshold = (
                CLAIM_REVOCATION
                if rails.POST_REVOCATION in first.reasons
                else CLAIM_NOTICE
            )
            state = REVERSED if claim_draw < threshold else EXPOSED
        else:
            state = CLEAN
        return Resolution(
            invoice_id=invoice.id,
            rail=invoice.rail,
            amount_minor=invoice.amount_minor,
            state=state,
            settle_day=first.day,
            due_day=invoice.due_day,
            days_late=first.day - invoice.due_day,
            reasons=first.reasons,
        )

    state = DECLINED if attempts else NOT_PRESENTED
    return Resolution(
        invoice_id=invoice.id,
        rail=invoice.rail,
        amount_minor=invoice.amount_minor,
        state=state,
        settle_day=None,
        due_day=invoice.due_day,
        days_late=None,
    )


def run(
    population: Population,
    planner: Planner,
    specs: dict[str, rails.RailSpec] | None = None,
) -> RunResult:
    """Execute one planner against one book, optionally with overridden rail rules."""
    subs = {sub.id: sub for sub in population.subscribers}
    table = specs if specs is not None else rails.RAILS
    result = RunResult(planner=planner.id)

    for invoice in population.invoices:
        subscriber = subs[invoice.subscriber_id]
        spec = table[invoice.rail]
        previous_day: int | None = None
        local: list[Attempt] = []

        for index in range(spec.max_attempts):
            day = planner.schedule_day(invoice, spec, index)
            if day > population.horizon_days:
                break
            if (
                planner.stops_on_revocation
                and subscriber.revoke_request_day is not None
                and day >= subscriber.revoke_request_day
            ):
                break
            attempt = present(
                invoice, subscriber, spec, planner, day, previous_day, population, index
            )
            local.append(attempt)
            if attempt.settled:
                break
            previous_day = day

        result.attempts.extend(local)
        result.resolutions.append(
            resolve(invoice, local, population.claim_draw.get(invoice.id, 1.0))
        )

    return result


def plan_all(
    population: Population,
    specs: dict[str, rails.RailSpec] | None = None,
) -> dict[str, RunResult]:
    return {
        planner_id: run(population, planner, specs)
        for planner_id, planner in PLANNERS.items()
    }
