"""Hold accounting. Integer cents, one invariant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Hold:
    auth_id: int
    authorized_cents: int
    approved_day: int
    captured_cents: int = 0
    released_cents: int = 0
    expired: bool = False

    @property
    def open_cents(self) -> int:
        """Money still held. A tolerance capture above the authorisation cannot go negative."""
        return max(0, self.authorized_cents - self.captured_cents - self.released_cents)


class AuthorisationLedger:
    """Authorise, capture, expire. Never lets captured exceed the allowed limit."""

    def __init__(self) -> None:
        self.holds: dict[int, Hold] = {}
        self.total_authorised = 0
        self.total_captured = 0
        self.total_released = 0
        self.refused_expired_cents = 0
        self.refused_tolerance_cents = 0
        self.refused_unknown_cents = 0
        self.captures_accepted = 0
        self.captures_refused = 0

    def authorise(self, auth_id: int, cents: int, day: int) -> None:
        if auth_id in self.holds:
            raise ValueError(f"duplicate authorisation {auth_id}")
        self.holds[auth_id] = Hold(auth_id=auth_id, authorized_cents=cents, approved_day=day)
        self.total_authorised += cents

    def limit_for(self, hold: Hold, tolerance_bp: int) -> int:
        """Allowed captured cents: authorised plus a tolerance in basis points."""
        return hold.authorized_cents + (hold.authorized_cents * tolerance_bp + 5_000) // 10_000

    def capture(self, auth_id: int, cents: int, tolerance_bp: int, overflow: str) -> dict:
        """Attempt a settlement. Returns what was accepted and what was refused."""
        hold = self.holds.get(auth_id)
        if hold is None:
            self.refused_unknown_cents += cents
            self.captures_refused += 1
            return {"status": "refused_unknown", "accepted": 0, "refused": cents}

        if hold.expired:
            self.refused_expired_cents += cents
            self.captures_refused += 1
            return {"status": "refused_expired", "accepted": 0, "refused": cents}

        room = self.limit_for(hold, tolerance_bp) - hold.captured_cents
        if cents <= room:
            hold.captured_cents += cents
            self.total_captured += cents
            self.captures_accepted += 1
            return {"status": "captured", "accepted": cents, "refused": 0}

        if overflow == "cap":
            accepted = max(0, room)
            hold.captured_cents += accepted
            self.total_captured += accepted
            refused = cents - accepted
            if accepted:
                self.captures_accepted += 1
            if refused:
                self.refused_tolerance_cents += refused
                self.captures_refused += 1
            return {"status": "capped", "accepted": accepted, "refused": refused}

        self.refused_tolerance_cents += cents
        self.captures_refused += 1
        return {"status": "refused_tolerance", "accepted": 0, "refused": cents}

    def expire(self, day: int, expiry_days: int | dict[int, int]) -> int:
        """Release every hold whose window closed at the end of `day`."""
        released = 0
        for hold in self.holds.values():
            if hold.expired or hold.open_cents <= 0:
                continue
            window = expiry_days.get(hold.auth_id, 10**9) if isinstance(expiry_days, dict) else expiry_days
            if day >= hold.approved_day + window:
                released += hold.open_cents
                hold.released_cents += hold.open_cents
                hold.expired = True
        self.total_released += released
        return released

    @property
    def open_cents(self) -> int:
        return sum(h.open_cents for h in self.holds.values())

    @property
    def captured_within_authorisation(self) -> int:
        return sum(min(h.captured_cents, h.authorized_cents) for h in self.holds.values())

    @property
    def captured_over_authorisation(self) -> int:
        """Cents collected above the authorised amount, inside the granted tolerance."""
        return sum(max(0, h.captured_cents - h.authorized_cents) for h in self.holds.values())

    def check_invariant(self) -> bool:
        """Two independent equalities, not a residual against zero.

        Authorised money is captured inside the authorisation, released, or still open.
        Anything captured above the authorisation is the tolerance, and is counted apart.
        """
        within = self.captured_within_authorisation
        over = self.captured_over_authorisation
        return (
            self.total_authorised == within + self.total_released + self.open_cents
            and self.total_captured == within + over
        )
