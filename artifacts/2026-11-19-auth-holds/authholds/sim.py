"""Day by day simulator over one book."""

from __future__ import annotations

from dataclasses import dataclass

from .book import Book
from .ledger import AuthorisationLedger
from .policy import Policy


@dataclass(frozen=True)
class Result:
    label: str
    policy: Policy
    requested_cents: int
    captured_cents: int
    refused_expired_cents: int
    refused_tolerance_cents: int
    refused_unknown_cents: int
    captures_accepted: int
    captures_refused: int
    expired_holds_with_remainder: int
    frozen_funds_cents_days: int
    invariant_ok: bool

    @property
    def capture_rate(self) -> float:
        if self.requested_cents == 0:
            return 0.0
        return self.captured_cents / self.requested_cents

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "expiry_days": self.policy.expiry_days,
            "tolerance_bp": self.policy.tolerance_bp,
            "overflow": self.policy.overflow,
            "expiry_by_kind": dict(self.policy.expiry_by_kind),
            "requested_cents": self.requested_cents,
            "captured_cents": self.captured_cents,
            "refused_expired_cents": self.refused_expired_cents,
            "refused_tolerance_cents": self.refused_tolerance_cents,
            "refused_unknown_cents": self.refused_unknown_cents,
            "captures_accepted": self.captures_accepted,
            "captures_refused": self.captures_refused,
            "expired_holds_with_remainder": self.expired_holds_with_remainder,
            "frozen_funds_cents_days": self.frozen_funds_cents_days,
            "capture_rate": round(self.capture_rate, 6),
            "invariant_ok": self.invariant_ok,
        }


def run(book: Book, policy: Policy, label: str = "") -> Result:
    """Process every day in order: measure open holds, authorise, capture, expire."""
    ledger = AuthorisationLedger()
    by_day: dict[int, list[int]] = {}
    for auth in book.auths:
        for capture in auth.captures:
            by_day.setdefault(capture.day, []).append(auth.auth_id)

    captures_by_auth = {a.auth_id: a.captures for a in book.auths}
    auths_by_id = {a.auth_id: a for a in book.auths}
    arrivals: dict[int, list[int]] = {}
    for auth in book.auths:
        arrivals.setdefault(auth.approved_day, []).append(auth.auth_id)

    frozen = 0
    accepted = 0
    expired_with_remainder = 0
    windows = (
        {a.auth_id: policy.expiry_for(a.kind) for a in book.auths}
        if policy.expiry_by_kind
        else policy.expiry_days
    )

    for day in range(book.horizon):
        # Stock at the start of the day: money the customer cannot spend yet.
        frozen += ledger.open_cents

        for auth_id in arrivals.get(day, ()):
            auth = auths_by_id[auth_id]
            ledger.authorise(auth_id, auth.authorized_cents, day)

        for auth_id in by_day.get(day, ()):
            for capture in captures_by_auth[auth_id]:
                if capture.day != day:
                    continue
                outcome = ledger.capture(auth_id, capture.cents, policy.tolerance_bp, policy.overflow)
                accepted += 1 if outcome["accepted"] else 0

        held_before = {h.auth_id: h.open_cents for h in ledger.holds.values() if h.open_cents > 0}
        ledger.expire(day, windows)
        for auth_id, before in held_before.items():
            if ledger.holds[auth_id].expired and before > 0:
                expired_with_remainder += 1

    return Result(
        label=label,
        policy=policy,
        requested_cents=book.requested_cents,
        captured_cents=ledger.total_captured,
        refused_expired_cents=ledger.refused_expired_cents,
        refused_tolerance_cents=ledger.refused_tolerance_cents,
        refused_unknown_cents=ledger.refused_unknown_cents,
        captures_accepted=ledger.captures_accepted,
        captures_refused=ledger.captures_refused,
        expired_holds_with_remainder=expired_with_remainder,
        frozen_funds_cents_days=frozen,
        invariant_ok=ledger.check_invariant(),
    )
