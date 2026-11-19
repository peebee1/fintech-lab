from authholds.book import generate_book
from authholds.policy import CEILING, DEFAULT, Policy
from authholds.sim import run

BOOK = generate_book(20261119)


def test_ceiling_captures_every_requested_cent():
    result = run(BOOK, CEILING)
    assert result.capture_rate == 1.0
    assert result.refused_expired_cents == 0
    assert result.refused_tolerance_cents == 0
    assert result.refused_unknown_cents == 0
    assert result.invariant_ok


def test_the_expiry_control_actually_binds():
    short = run(BOOK, Policy(expiry_days=3, tolerance_bp=DEFAULT.tolerance_bp))
    long = run(BOOK, Policy(expiry_days=28, tolerance_bp=DEFAULT.tolerance_bp))
    assert short.refused_expired_cents > 0
    assert short.capture_rate < 0.95
    assert long.capture_rate > short.capture_rate


def test_longer_holds_never_decline_more_and_never_freeze_less():
    rates = []
    frozen = []
    for days in (1, 3, 7, 14, 28):
        result = run(BOOK, Policy(expiry_days=days, tolerance_bp=1500))
        rates.append(result.capture_rate)
        frozen.append(result.frozen_funds_cents_days)
    assert rates == sorted(rates)
    assert frozen == sorted(frozen)


def test_captures_stay_inside_the_authorised_ceiling():
    policy = Policy(expiry_days=7, tolerance_bp=0)
    result = run(BOOK, policy)
    over = [
        a
        for a in BOOK.auths
        if a.kind == "restaurant" and a.captures and a.requested_cents > a.authorized_cents
    ]
    assert over, "the book must contain tip captures above the authorisation"
    assert result.refused_tolerance_cents > 0
    assert result.invariant_ok


def test_tolerance_binds_on_tips():
    zero = run(BOOK, Policy(expiry_days=7, tolerance_bp=0))
    fifteen = run(BOOK, Policy(expiry_days=7, tolerance_bp=1500))
    assert zero.refused_tolerance_cents > fifteen.refused_tolerance_cents
    assert fifteen.captured_cents > zero.captured_cents


def test_simulation_is_deterministic():
    first = run(BOOK, DEFAULT).as_dict()
    second = run(BOOK, DEFAULT).as_dict()
    assert first == second


def test_horizon_leaves_no_case_unresolved():
    result = run(BOOK, Policy(expiry_days=28, tolerance_bp=1500))
    assert result.refused_unknown_cents == 0
    assert result.invariant_ok
