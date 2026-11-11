"""Business day arithmetic for network deadlines.

A network deadline expressed in calendar days that lands on a non processing
day is pushed to the next processing day. Getting this wrong by one day is the
difference between a representment and a loss, and it only bites on the boundary.
"""

from __future__ import annotations

from datetime import date, timedelta

# Synthetic processing calendar. Fixed, so the artifact never depends on the
# clock and the suite cannot rot.
NETWORK_HOLIDAYS = frozenset(
    {
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 5, 25),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    }
)


def is_business_day(day: date, holidays: frozenset[date] = NETWORK_HOLIDAYS) -> bool:
    return day.weekday() < 5 and day not in holidays


def roll_forward(day: date, holidays: frozenset[date] = NETWORK_HOLIDAYS) -> date:
    """Advance to the next processing day, or return the day unchanged."""
    guard = 0
    while not is_business_day(day, holidays):
        day += timedelta(days=1)
        guard += 1
        if guard > 14:
            raise ValueError("no processing day found within two weeks")
    return day


def business_days_between(start: date, end: date, holidays: frozenset[date] = NETWORK_HOLIDAYS) -> int:
    """Processing days in (start, end]. Negative when end is before start."""
    if end == start:
        return 0
    sign = 1 if end > start else -1
    lo, hi = (start, end) if end > start else (end, start)
    count = 0
    day = lo
    while day < hi:
        day += timedelta(days=1)
        if is_business_day(day, holidays):
            count += 1
    return sign * count


def add_window(start: date, days: int, holidays: frozenset[date] = NETWORK_HOLIDAYS) -> date:
    """A deadline: start plus calendar days, pushed off non processing days."""
    return roll_forward(start + timedelta(days=days), holidays)
