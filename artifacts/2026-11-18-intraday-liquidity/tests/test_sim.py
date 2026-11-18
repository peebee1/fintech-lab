"""The simulator: the required balance is exactly sufficient, and the cost adds up."""

from __future__ import annotations

from liquidity.book import Event, Day
from liquidity.sim import (
    carry_cost_cents,
    day_cost_cents,
    required_opening,
    simulate_day,
    totals,
)


def hand_day(opening_events: list[Event], index: int = 0) -> Day:
    inflows = sum(e.cents for e in opening_events if e.kind == "inflow")
    payouts = sum(e.cents for e in opening_events if e.kind == "payout")
    payout_events = [e for e in opening_events if e.kind == "payout"]
    return Day(
        index=index,
        card_cents=0,
        inflow_cents=inflows,
        payout_cents=payouts,
        first_batch_cents=payout_events[0].cents if payout_events else 0,
        second_batch_cents=payout_events[1].cents if len(payout_events) > 1 else 0,
        early_inflow_cents=0,
        late_inflow_cents=0,
        slipped_in_cents=0,
        events=tuple(sorted(opening_events, key=lambda e: e.minute)),
    )


def test_required_opening_on_a_hand_day():
    # 09:00 inflow 100, 11:00 payout 250, 15:00 payout 200, 16:30 inflow 400.
    day = hand_day(
        [
            Event(540, "inflow", 100),
            Event(660, "payout", 250),
            Event(900, "payout", 200),
            Event(990, "inflow", 400),
        ]
    )
    # At 11:00 the account needs 150 (250 due, 100 arrived). At 15:00 the
    # cumulative requirement is 450 - 100 = 350. The requirement is the worst.
    assert required_opening(day) == 350


def test_requirement_is_exactly_sufficient_on_every_day(short_book):
    """One cent less must short. This is the invariant, not a zero check."""
    for day in short_book:
        need = required_opening(day)
        funded = simulate_day(day, need)
        assert funded.events == 0, day.index
        assert funded.gap_cents == 0
        if need > 0:
            short = simulate_day(day, need - 1)
            assert short.events >= 1, day.index
            assert short.gap_cents >= 1


def test_simulate_day_walks_the_clock():
    day = hand_day(
        [
            Event(540, "inflow", 50),
            Event(660, "payout", 60),
            Event(900, "payout", 90),
            Event(990, "inflow", 500),
        ]
    )
    result = simulate_day(day, 100)
    # 09:00 balance 150, 11:00 pays 60 leaving 90, 15:00 owes 90 and has exactly
    # 90, so nothing fails. At 99 it would short by one cent at 15:00.
    assert result.events == 0
    assert result.gap_cents == 0
    short = simulate_day(day, 99)
    assert short.events == 1
    assert short.gap_cents == 1


def test_a_shortfall_covers_the_gap_and_keeps_going():
    day = hand_day([Event(660, "payout", 80), Event(900, "payout", 80)])
    result = simulate_day(day, 0)
    assert result.events == 2
    assert result.gap_cents == 160


def test_costs_add_up_to_the_total():
    day = hand_day([Event(660, "payout", 800_000), Event(900, "payout", 400_000)])
    results = [simulate_day(day, 0), simulate_day(day, 1_000_000)]
    t = totals(results, fee_cents=25_000, emergency_bps=10.0, carry_bps=2.18)
    assert t["total_cents"] == t["carry_cents"] + t["fee_cents"] + t["emergency_cents"]
    # Independently: opening zero fails both batches, opening one million cents
    # pays the first and shorts 200,000 cents on the second. Three failed batches
    # at 250 dollars, 1,400,000 cents of gap at 10 bps, a million cents held one
    # day at 2.18 bps.
    assert t["fee_cents"] == 3 * 25_000
    assert t["emergency_cents"] == round(1_400_000 * 10.0 / 10_000.0)
    assert t["carry_cents"] == round(1_000_000 * 2.18 / 10_000.0)
    assert t["events"] == 3
    assert t["days_shorted"] == 2


def test_day_cost_is_fees_plus_facility():
    day = hand_day([Event(660, "payout", 1_000_000)])
    result = simulate_day(day, 400_000)
    assert day_cost_cents(result, fee_cents=25_000, emergency_bps=10.0) == 25_000 + 600


def test_carry_is_a_daily_rate_not_an_annual_one():
    assert carry_cost_cents(100_000_000) == round(100_000_000 * 2.18 / 10_000.0)
