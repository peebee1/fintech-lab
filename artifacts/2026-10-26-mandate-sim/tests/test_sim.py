import pytest

from mandate.model import (
    CLEAN,
    DECLINED,
    DECLINED_AFA,
    DECLINED_FUNDS,
    DECLINED_REVOKED,
    DECLINED_TOO_SOON,
    EXPOSED,
    NOT_PRESENTED,
    REVERSED,
    Invoice,
    Subscriber,
)
from mandate.rails import NOTICE_SHORT
from mandate.sim import PLANNERS, build_population, run


def test_naive_schedules_on_the_due_date_for_every_rail(one):
    for rail in ("card", "sepa", "upi"):
        population = one(rail, due=20)
        attempt = run(population, PLANNERS["naive"]).attempts[0]
        assert attempt.day == 20


def test_naive_sepa_debit_is_refundable_without_notice(one):
    population = one("sepa", issued=0, due=20)
    resolution = run(population, PLANNERS["naive"]).resolutions[0]
    assert resolution.state == EXPOSED
    assert resolution.reasons == (NOTICE_SHORT,)


def test_naive_card_debit_carries_no_refund_right(one):
    population = one("card", issued=0, due=20)
    resolution = run(population, PLANNERS["naive"]).resolutions[0]
    assert resolution.state == CLEAN
    assert resolution.reasons == ()


def test_compliant_sepa_waits_out_the_notice_window(one, book):
    population = one("sepa", issued=20, due=20)
    resolution = run(population, PLANNERS["rail_aware"]).resolutions[0]
    assert resolution.state == CLEAN
    assert resolution.settle_day == 34
    assert resolution.days_late == 14


def test_compliant_retry_serves_a_fresh_notice(one, book):
    # Funds are short on the first two compatible days, so the retry has to wait
    # two days plus a fresh 14 day notice.
    population = one("sepa", issued=0, due=40)
    population = type(population)(
        subscribers=population.subscribers,
        invoices=population.invoices,
        short_days={"s1": frozenset({40})},
        afa_approved=population.afa_approved,
        claim_draw=population.claim_draw,
        horizon_days=120,
        seed=0,
    )
    attempts = run(population, PLANNERS["rail_aware"]).attempts
    assert [a.day for a in attempts] == [40, 56]
    assert attempts[0].outcome == DECLINED_FUNDS
    assert attempts[1].outcome == "settled"


def test_plain_ladder_on_sepa_never_recovers_because_every_retry_is_too_soon(book):
    sub = Subscriber(id="s1", rail="sepa", amount_minor=1999, due_day=20)
    invoice = Invoice("i1", "s1", "sepa", 1999, 0, 20, 0)
    population = book([invoice], [sub], short_days={"s1": frozenset({20})})
    attempts = run(population, PLANNERS["naive"]).attempts
    assert [a.outcome for a in attempts] == [
        DECLINED_FUNDS,
        DECLINED_TOO_SOON,
        DECLINED_TOO_SOON,
    ]


def test_over_cap_upi_is_lost_when_the_planner_does_not_ask(one):
    population = one("upi", amount=1_899_900)
    resolution = run(population, PLANNERS["naive"]).resolutions[0]
    assert resolution.state == DECLINED
    assert run(population, PLANNERS["naive"]).attempts[0].outcome == DECLINED_AFA


def test_over_cap_upi_settles_when_the_payer_authenticates(one):
    population = one("upi", amount=1_899_900)
    resolution = run(population, PLANNERS["rail_aware"]).resolutions[0]
    assert resolution.state == CLEAN


def test_revocation_is_respected_at_request_time_not_at_rail_time(book):
    sub = Subscriber(id="s1", rail="sepa", amount_minor=1999, due_day=30, revoke_request_day=25)
    invoice = Invoice("i1", "s1", "sepa", 1999, 0, 30, 0)
    population = book([invoice], [sub])

    compliant = run(population, PLANNERS["rail_aware"]).resolutions[0]
    assert compliant.state == NOT_PRESENTED

    naive = run(population, PLANNERS["naive"])
    assert naive.attempts[0].outcome == DECLINED_REVOKED


def test_nothing_is_presented_past_the_horizon(book):
    sub = Subscriber(id="s1", rail="sepa", amount_minor=1999, due_day=88)
    invoice = Invoice("i1", "s1", "sepa", 1999, 0, 88, 0)
    population = book(
        [invoice], [sub], short_days={"s1": frozenset({88})}, horizon_days=90
    )
    result = run(population, PLANNERS["rail_aware"])
    # The retry would land on day 104, past the horizon, so it is never presented.
    assert [a.day for a in result.attempts] == [88]
    assert result.attempts[0].outcome == DECLINED_FUNDS
    assert result.resolutions[0].state == DECLINED


@pytest.mark.parametrize(
    "claim_draw, expected",
    [(1.0, EXPOSED), (0.0, REVERSED)],
)
def test_a_refund_right_only_becomes_a_reversal_if_the_payer_acts(book, claim_draw, expected):
    sub = Subscriber(id="s1", rail="sepa", amount_minor=1999, due_day=20)
    invoice = Invoice("i1", "s1", "sepa", 1999, 0, 20, 0)
    population = book([invoice], [sub], claim_draw=claim_draw)
    assert run(population, PLANNERS["naive"]).resolutions[0].state == expected


def test_no_compliant_presentation_is_ever_reversible():
    population = build_population(seed=5, subscribers=250)
    result = run(population, PLANNERS["rail_aware"])
    assert result.attempts
    assert [a for a in result.attempts if a.reversible] == []
    assert all(r.state not in (EXPOSED, REVERSED) for r in result.resolutions)
