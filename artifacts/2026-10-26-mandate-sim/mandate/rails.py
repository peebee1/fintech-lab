"""Rail rules, modelled from the public rulebooks.

Every field is a parameter, not a claim of regulatory compliance: change the
table and the eval recomputes. What is modelled is the part of each rule that
changes what a scheduler may do, and when.

- SEPA direct debit: the creditor notifies the payer at least 14 calendar days
  before a C2B collection (core rulebook, recurring series), and the payer keeps
  an unconditional refund right for 8 weeks from the debit date. A re-presentment
  is a new collection, so it is notified again.
- Card recurring (merchant initiated): a fixed amount mandate needs no per debit
  pre-notification, so the rail looks forgiving. The exposure is the scheme
  chargeback window.
- UPI autopay, India: 24 hours pre-debit notification and an AFA free ceiling of
  INR 15,000 per debit. Source: RBI Digital Payments E-mandate Framework, 21
  April 2026.
"""

from __future__ import annotations

from dataclasses import dataclass

NOTICE_SHORT = "notice_short"
POST_REVOCATION = "post_revocation"


@dataclass(frozen=True)
class RailSpec:
    id: str
    label: str
    currency: str
    prenotify_days: int
    retry_gap_days: int
    max_attempts: int
    afa_free_cap_minor: int | None
    dispute_window_days: int
    revoke_lag_days: int
    retry_needs_notice: bool

    def needs_afa(self, amount_minor: int) -> bool:
        """True when the rail will not process this debit without the payer authenticating."""
        return self.afa_free_cap_minor is not None and amount_minor > self.afa_free_cap_minor

    def first_day(self, due_day: int, issued_day: int) -> int:
        """Earliest day a compliant scheduler can present this invoice."""
        return max(due_day, issued_day + self.prenotify_days)

    def retry_lead(self) -> int:
        """Extra days a retry needs beyond the base retry gap."""
        return self.prenotify_days if self.retry_needs_notice else 0


RAILS: dict[str, RailSpec] = {
    "card": RailSpec(
        id="card",
        label="Card recurring",
        currency="EUR",
        prenotify_days=0,
        retry_gap_days=1,
        max_attempts=3,
        afa_free_cap_minor=None,
        dispute_window_days=120,
        revoke_lag_days=0,
        retry_needs_notice=False,
    ),
    "sepa": RailSpec(
        id="sepa",
        label="SEPA direct debit",
        currency="EUR",
        prenotify_days=14,
        retry_gap_days=2,
        max_attempts=3,
        afa_free_cap_minor=None,
        dispute_window_days=56,
        revoke_lag_days=1,
        retry_needs_notice=True,
    ),
    "upi": RailSpec(
        id="upi",
        label="UPI autopay",
        currency="INR",
        prenotify_days=1,
        retry_gap_days=1,
        max_attempts=3,
        afa_free_cap_minor=1_500_000,
        dispute_window_days=30,
        revoke_lag_days=1,
        retry_needs_notice=True,
    ),
}


def get(rail_id: str) -> RailSpec:
    return RAILS[rail_id]


def violation_reasons(
    spec: RailSpec,
    attempt_day: int,
    notice_day: int,
    revoke_request_day: int | None,
    revoke_effective_day: int | None,
) -> tuple[str, ...]:
    """Reasons a settled debit could be clawed back by the payer.

    A debit presented before its notification window has run is refundable even
    if the payer never complained. A debit presented in the gap between the payer
    asking to stop and the mandate actually stopping settles, then comes back.
    """
    reasons: list[str] = []
    if attempt_day - notice_day < spec.prenotify_days:
        reasons.append(NOTICE_SHORT)
    if revoke_request_day is not None and attempt_day >= revoke_request_day:
        if revoke_effective_day is None or attempt_day < revoke_effective_day:
            reasons.append(POST_REVOCATION)
    return tuple(reasons)
