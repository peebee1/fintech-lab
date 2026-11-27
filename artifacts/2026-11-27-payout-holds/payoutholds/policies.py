"""Payout policy terms: when money leaves, and how much of it is held back."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    name: str
    hold_days: int = 1
    reserve_rate: float = 0.0
    reserve_days: int = 0
    clawback: bool = True
    tiered: bool = False
    tier_variant: str = "hold_plus_reserve"
    note: str = ""

    def terms(self, band: str, tenure_days: int) -> tuple[int, float, int]:
        """Resolve hold days, reserve rate and reserve days for one sale."""
        if self.tiered:
            if band == "established" and tenure_days >= 90:
                return (2, 0.0, 0)
            if self.tier_variant == "reserve_only":
                return (1, 0.20, 60)
            return (14, 0.10, 60)
        return (self.hold_days, self.reserve_rate, self.reserve_days)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "hold_days": self.hold_days,
            "reserve_rate": round(self.reserve_rate, 4),
            "reserve_days": self.reserve_days,
            "clawback": self.clawback,
            "tiered": self.tiered,
            "tier_variant": self.tier_variant,
            "note": self.note,
        }


LADDER = [
    Policy("pay_t1", hold_days=1, note="pay next day, no reserve: what sellers ask for"),
    Policy("hold_7", hold_days=7, note="one week hold, no reserve"),
    Policy("hold_14", hold_days=14, note="two week hold, no reserve"),
    Policy("hold_21", hold_days=21, note="three week hold, no reserve"),
    Policy("reserve_5", reserve_rate=0.05, reserve_days=30, note="5 percent held 30 days"),
    Policy("reserve_10", reserve_rate=0.10, reserve_days=30, note="10 percent held 30 days"),
    Policy("reserve_20", reserve_rate=0.20, reserve_days=30, note="20 percent held 30 days"),
    Policy("hold_7_reserve_10", hold_days=7, reserve_rate=0.10, reserve_days=30),
    Policy(
        "reserve_10_no_clawback",
        reserve_rate=0.10,
        reserve_days=30,
        clawback=False,
        note="the reserve pays refunds but later sales are never withheld",
    ),
    Policy(
        "tiered_hold",
        tiered=True,
        note="new and risky: 14 day hold plus 10 percent for 60 days; established: T+2",
    ),
    Policy(
        "tiered_reserve",
        tiered=True,
        tier_variant="reserve_only",
        note="new and risky: 20 percent for 60 days, no hold; established: T+1",
    ),
]

RESERVE_SWEEP = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
HOLD_SWEEP = [0, 3, 7, 14, 21, 28]
