"""Policies as pure decision functions.

A policy sees the site, the day, the inventory at the start of the day and one
forecast number. It returns how many notes to have delivered before demand. It
does not see demand, the book, or the result of any other site.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .book import Site
from .forecast import actual_daily, trailing_daily

MON_THU = (0, 3)


@dataclass(frozen=True)
class Policy:
    name: str
    trigger_days: float
    fill_days: float  # math.inf means fill to capacity
    schedule: str  # "any", "site_weekday", "site_fortnight", "mon_thu"
    emergency: bool
    forecast: str
    label: str

    def forecast_notes(self, book, site: Site, day: int) -> int:
        if self.forecast == "actual":
            return actual_daily(book, site, day)
        return trailing_daily(book, site, day)

    def allowed_on(self, site: Site, day: int) -> bool:
        if self.schedule == "any":
            return True
        if self.schedule == "site_weekday":
            return day % 7 == site.schedule_weekday
        if self.schedule == "site_fortnight":
            return day % 14 == site.schedule_weekday
        return day % 7 in MON_THU

    def decide(self, site: Site, day: int, inventory: int, forecast: int) -> tuple[int, bool]:
        """Return (notes to deliver, whether the trip is an emergency trip)."""
        target = site.capacity if math.isinf(self.fill_days) else inventory + math.ceil(
            forecast * self.fill_days
        )
        deliver = max(0, min(site.capacity, target) - inventory)
        if deliver <= 0:
            return 0, False

        if self.allowed_on(site, day):
            if math.isinf(self.trigger_days) or inventory < self.trigger_days * forecast:
                return deliver, False
            return 0, False
        if self.emergency and inventory < forecast:
            return deliver, True
        return 0, False


POLICIES: tuple[Policy, ...] = (
    Policy(
        name="fixed_week_capacity",
        trigger_days=math.inf,
        fill_days=math.inf,
        schedule="site_weekday",
        emergency=False,
        forecast="trailing",
        label="one trip a week on the site's weekday, fill to capacity",
    ),
    Policy(
        name="fixed_week_cover",
        trigger_days=math.inf,
        fill_days=7.0,
        schedule="site_weekday",
        emergency=False,
        forecast="trailing",
        label="one trip a week, fill to seven forecast days",
    ),
    Policy(
        name="fixed_fortnight_cover",
        trigger_days=math.inf,
        fill_days=13.0,
        schedule="site_fortnight",
        emergency=False,
        forecast="trailing",
        label="one trip a fortnight, fill to thirteen forecast days",
    ),
    Policy(
        name="minmax_3_6",
        trigger_days=3.0,
        fill_days=6.0,
        schedule="any",
        emergency=False,
        forecast="trailing",
        label="any day, trip when cover falls under three days, fill to six",
    ),
    Policy(
        name="calendar_two_runs",
        trigger_days=5.0,
        fill_days=9.0,
        schedule="mon_thu",
        emergency=True,
        forecast="trailing",
        label="Monday and Thursday runs only, trigger five days, emergency trip at premium",
    ),
    Policy(
        name="oracle_minmax",
        trigger_days=2.0,
        fill_days=5.0,
        schedule="any",
        emergency=False,
        forecast="actual",
        label="perfect foresight reference, trip when cover falls under two days",
    ),
)

PRACTICAL = tuple(p for p in POLICIES if p.name != "oracle_minmax")
BY_NAME = {p.name: p for p in POLICIES}
