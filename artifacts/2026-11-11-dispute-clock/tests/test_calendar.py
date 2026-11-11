from datetime import date, timedelta

from disputeclock import netcalendar


def test_weekend_rolls_to_monday():
    # 2026-01-10 is a Saturday, 2026-01-12 the following Monday.
    assert netcalendar.roll_forward(date(2026, 1, 10)) == date(2026, 1, 12)
    assert netcalendar.roll_forward(date(2026, 1, 11)) == date(2026, 1, 12)


def test_business_day_is_unchanged():
    assert netcalendar.roll_forward(date(2026, 1, 13)) == date(2026, 1, 13)


def test_holiday_rolls_forward():
    # 2026-01-19 is a processing holiday in the synthetic calendar, a Monday.
    assert not netcalendar.is_business_day(date(2026, 1, 19))
    assert netcalendar.roll_forward(date(2026, 1, 19)) == date(2026, 1, 20)


def test_add_window_is_the_first_processing_day_at_or_after_the_calendar_deadline():
    for offset in range(0, 120):
        start = date(2026, 2, 1) + timedelta(days=offset)
        for window in (20, 30, 45):
            deadline = netcalendar.add_window(start, window)
            naive = start + timedelta(days=window)
            assert deadline >= naive
            assert netcalendar.is_business_day(deadline)
            assert (deadline - naive).days <= 3
            # nothing earlier than the deadline is a processing day at or after it
            earlier = naive
            while earlier < deadline:
                assert not netcalendar.is_business_day(earlier)
                earlier += timedelta(days=1)


def test_business_days_between_counts_weekdays_only():
    # Monday to the next Monday is five processing days.
    assert netcalendar.business_days_between(date(2026, 3, 2), date(2026, 3, 9)) == 5
    assert netcalendar.business_days_between(date(2026, 3, 9), date(2026, 3, 2)) == -5
    assert netcalendar.business_days_between(date(2026, 3, 2), date(2026, 3, 2)) == 0
