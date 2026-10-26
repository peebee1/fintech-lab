"""Records: subscribers, invoices, presentations, and per invoice resolution.

Days are integers counted from day 0 of the simulation horizon. Nothing here
reads a wall clock, so two runs of the same seed are identical.

A settled debit can be in one of three billing states. Compliant, so the payer
has no claim. Reversible but unclaimed, which is exposure: the right exists and
the money is still in the account. Or reversed, which is the right exercised.
Keeping those apart is the difference between measuring a risk and asserting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# One presentation outcome, and exactly one.
SETTLED = "settled"
DECLINED_FUNDS = "declined_funds"
DECLINED_AFA = "declined_afa"
DECLINED_REVOKED = "declined_revoked"
DECLINED_TOO_SOON = "declined_too_soon"

DECLINES = (DECLINED_FUNDS, DECLINED_AFA, DECLINED_REVOKED, DECLINED_TOO_SOON)

# Resolution states. Every invoice lands in exactly one, and the five buckets sum
# to the billed amount.
CLEAN = "clean"
EXPOSED = "exposed"
REVERSED = "reversed"
DECLINED = "declined"
NOT_PRESENTED = "not_presented"

STATES = (CLEAN, EXPOSED, REVERSED, DECLINED, NOT_PRESENTED)

# Collected today, whether or not the payer could still ask for it back.
COLLECTED_STATES = (CLEAN, EXPOSED)


@dataclass(frozen=True)
class Subscriber:
    id: str
    rail: str
    amount_minor: int
    due_day: int
    revoke_request_day: int | None = None

    def revoke_effective_day(self, lag_days: int) -> int | None:
        if self.revoke_request_day is None:
            return None
        return self.revoke_request_day + lag_days


@dataclass(frozen=True)
class Invoice:
    id: str
    subscriber_id: str
    rail: str
    amount_minor: int
    issued_day: int
    due_day: int
    cycle: int


@dataclass(frozen=True)
class Attempt:
    invoice_id: str
    rail: str
    day: int
    amount_minor: int
    index: int
    notice_day: int
    outcome: str
    reasons: tuple[str, ...] = ()

    @property
    def settled(self) -> bool:
        return self.outcome == SETTLED

    @property
    def reversible(self) -> bool:
        return self.outcome == SETTLED and bool(self.reasons)


@dataclass(frozen=True)
class Population:
    subscribers: tuple[Subscriber, ...]
    invoices: tuple[Invoice, ...]
    short_days: dict[str, frozenset[int]]
    afa_approved: dict[tuple[str, int], bool]
    claim_draw: dict[str, float]
    horizon_days: int
    seed: int


@dataclass(frozen=True)
class Resolution:
    invoice_id: str
    rail: str
    amount_minor: int
    state: str
    settle_day: int | None
    due_day: int
    days_late: int | None
    reasons: tuple[str, ...] = ()

    @property
    def kept_minor(self) -> int:
        """Money still kept, after the reversals that actually happened."""
        return self.amount_minor if self.state in COLLECTED_STATES else 0


@dataclass
class RunResult:
    planner: str
    attempts: list[Attempt] = field(default_factory=list)
    resolutions: list[Resolution] = field(default_factory=list)
