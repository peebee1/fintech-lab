"""Capture-window policies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    """How long a hold lives, and how far above it a capture may land.

    expiry_days: the hold is live through the end of approved_day + expiry_days.
    tolerance_bp: allowed capture headroom over the authorised amount, basis points.
    overflow: "refuse" rejects an over-limit capture, "cap" settles what fits.
    """

    expiry_days: int
    tolerance_bp: int
    overflow: str = "refuse"
    expiry_by_kind: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if self.expiry_days < 0:
            raise ValueError("expiry_days must be non negative")
        if self.tolerance_bp < 0:
            raise ValueError("tolerance_bp must be non negative")
        if self.overflow not in {"refuse", "cap"}:
            raise ValueError(f"unknown overflow mode {self.overflow}")
        for _, days in self.expiry_by_kind:
            if days < 0:
                raise ValueError("per kind expiry must be non negative")

    def expiry_for(self, kind: str) -> int:
        for name, days in self.expiry_by_kind:
            if name == kind:
                return days
        return self.expiry_days


DEFAULT = Policy(expiry_days=7, tolerance_bp=1500)
CEILING = Policy(expiry_days=10_000, tolerance_bp=100_000)

# One window per merchant class, sized to the capture habit rather than the calendar.
TIERED = Policy(
    expiry_days=7,
    tolerance_bp=1500,
    expiry_by_kind=(("restaurant", 7), ("retail", 7), ("split", 14), ("hotel", 21), ("late", 21)),
)

EXPIRY_SWEEP = (1, 2, 3, 5, 7, 10, 14, 21, 28)
TOLERANCE_SWEEP = (0, 500, 1000, 1500, 2000, 2500)
