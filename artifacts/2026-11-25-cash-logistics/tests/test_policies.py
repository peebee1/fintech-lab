"""Policy decisions are pure, and the forecast never reads the future."""

from dataclasses import replace

import pytest

from cashplan.book import Book, Site, generate
from cashplan.forecast import trailing_daily
from cashplan.policies import BY_NAME, Policy


def _site(kind="metro"):
    return next(s for s in generate(days=5).sites if s.kind == kind)


def test_weekly_policy_only_trips_on_its_own_weekday():
    site = _site()
    policy = BY_NAME["fixed_week_capacity"]
    for day in range(14):
        order, emergency = policy.decide(site, day, inventory=0, forecast=100)
        if day % 7 == site.schedule_weekday:
            assert order == site.capacity
            assert not emergency
        else:
            assert order == 0


def test_fill_is_capped_at_capacity_and_zero_when_full():
    site = _site()
    policy = Policy(
        name="t",
        trigger_days=3.0,
        fill_days=6.0,
        schedule="any",
        emergency=False,
        forecast="trailing",
        label="test",
    )
    assert policy.decide(site, 0, inventory=0, forecast=10**6)[0] == site.capacity
    assert policy.decide(site, 0, inventory=site.capacity, forecast=10)[0] == 0
    # Cover is nearly exhausted against this forecast, so the cap is what limits the order.
    assert policy.decide(site, 0, inventory=site.capacity - 5, forecast=10**6)[0] == 5


def test_minmax_triggers_on_cover_days():
    site = _site()
    policy = BY_NAME["minmax_3_6"]
    forecast = 100
    # 350 notes is 3.5 days of cover, above the trigger, so no trip.
    assert policy.decide(site, 0, inventory=350, forecast=forecast) == (0, False)
    # 250 notes is 2.5 days, so it trips and fills to six days.
    order, emergency = policy.decide(site, 0, inventory=250, forecast=forecast)
    assert order == 600  # 250 held plus six forecast days of 100, all of it delivered
    assert not emergency


def test_emergency_trip_only_off_schedule_and_only_when_survival_is_doubtful():
    site = _site()
    policy = BY_NAME["calendar_two_runs"]
    saturday = next(day for day in range(7) if day % 7 not in (0, 3))
    order, emergency = policy.decide(site, saturday, inventory=10, forecast=100)
    assert emergency and order > 0
    order, emergency = policy.decide(site, saturday, inventory=500, forecast=100)
    assert order == 0


def test_forecast_ignores_the_day_itself_and_every_day_after(book):
    site = book.sites[0]
    day = 40
    base = trailing_daily(book, site, day)

    rows = list(book.rows[site.id])
    for index in range(day, len(rows)):
        rows[index] = replace(rows[index], notes=10**9, withdrawals=10**6)
    tampered = Book(sites=book.sites, rows={**book.rows, site.id: tuple(rows)}, days=book.days, seed=book.seed)
    assert trailing_daily(tampered, site, day) == base


def test_forecast_moves_when_history_moves(book):
    site = book.sites[1]
    day = 40
    base = trailing_daily(book, site, day)
    rows = list(book.rows[site.id])
    index = max(i for i in range(day) if i % 7 == day % 7)
    rows[index] = replace(rows[index], notes=rows[index].notes + 10_000)
    changed = Book(sites=book.sites, rows={**book.rows, site.id: tuple(rows)}, days=book.days, seed=book.seed)
    assert trailing_daily(changed, site, day) > base


def test_forecast_at_day_zero_falls_back_to_the_site_base_load(book):
    site = book.sites[0]
    value = trailing_daily(book, site, 0)
    assert value >= 1
    assert value == pytest.approx(site.base_notes * 1.10, rel=0.05)
