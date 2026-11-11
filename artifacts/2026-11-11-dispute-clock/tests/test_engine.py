import pytest

from disputeclock import engine
from disputeclock.model import WON_STATES, State


def _contest_states(result):
    return [s for s in result.states if State.SUBMITTED in s.trace]


def test_illegal_transition_is_refused(book):
    st = engine.CaseState(case=book.cases[0], deadline=book.cases[0].arrival)
    with pytest.raises(ValueError):
        st.move(State.WON)


def test_zero_budget_blocks_all_evidence_work(book):
    result = engine.run(book, engine.ThreeClock(), budget_per_day=0)
    assert result.minutes == 0
    assert _contest_states(result) == []
    assert result.skipped > 0, "the queue should have demanded more than zero minutes"


def test_auto_wins_cost_no_analyst_time(book):
    result = engine.run(book, engine.FreesAdded(), budget_per_day=10_000)
    auto = [s for s in result.states if s.state is State.AUTO_WON]
    assert auto
    assert all(s.minutes == 0 for s in auto)
    assert all(s.case.free_win for s in auto)


def test_status_only_breaks_on_the_short_window_only(book):
    row = engine.run(book, engine.StatusOnly(), budget_per_day=10_000).stats()
    assert row["forfeited_fraud_cases"] > 0
    assert row["forfeited_service_cases"] == 0


def test_status_only_never_wins_a_fraud_dispute(book):
    """Its own three week habit is longer than the twenty day fraud window."""
    result = engine.run(book, engine.StatusOnly(), budget_per_day=10_000)
    fraud_wins = [
        s for s in result.states if s.case.reason.is_fraud and s.state in WON_STATES
    ]
    assert fraud_wins == []


def test_modelling_the_clock_recovers_more_than_a_status_tracker(book):
    status = engine.run(book, engine.StatusOnly(), budget_per_day=40).stats()
    clock = engine.run(book, engine.ResponseClock(), budget_per_day=40).stats()
    assert clock["recovered_usd"] > status["recovered_usd"]
    assert clock["forfeited_cases"] < status["forfeited_cases"]


def test_never_won_more_than_was_defensible(book):
    ceiling = sum(c.amount_minor for c in book.cases if c.defensible)
    for policy in (engine.StatusOnly(), engine.ResponseClock(), engine.ThreeClock()):
        result = engine.run(book, policy, budget_per_day=40)
        assert result.recovered_minor <= ceiling


def test_every_run_resolves_every_case(book):
    for policy in (engine.StatusOnly(), engine.ThreeClock()):
        result = engine.run(book, policy, budget_per_day=40)
        assert len(result.states) == len(book.cases)
        assert {s.case.id for s in result.states} == {c.id for c in book.cases}


def test_pushback_is_only_opened_for_a_won_case(book):
    result = engine.run(book, engine.ThreeClock(), budget_per_day=40)
    for st in result.states:
        if st.pushback_day is not None:
            assert State.WON in st.trace
            assert st.case.pre_arb
