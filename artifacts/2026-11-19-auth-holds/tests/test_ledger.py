import pytest

from authholds.ledger import AuthorisationLedger


def build() -> AuthorisationLedger:
    ledger = AuthorisationLedger()
    ledger.authorise(1, 10_000, 0)
    ledger.authorise(2, 5_000, 0)
    return ledger


def test_invariant_holds_on_dirty_data():
    ledger = build()
    ledger.capture(1, 9_000, 1_500, "refuse")
    ledger.capture(1, 2_500, 1_500, "refuse")  # fits exactly in the 15 percent headroom
    ledger.capture(2, 50_000, 1_500, "refuse")  # refused entirely
    ledger.capture(99, 1_000, 1_500, "refuse")  # unknown authorisation
    ledger.expire(7, 7)
    assert ledger.check_invariant()
    # independent totals, not residual == 0
    assert ledger.total_authorised == 15_000
    assert ledger.total_captured == 11_500
    assert ledger.captured_within_authorisation == 10_000
    assert ledger.captured_over_authorisation == 1_500
    assert ledger.total_released == 5_000
    assert ledger.open_cents == 0


def test_capture_can_never_exceed_the_tolerance_ceiling():
    ledger = build()
    ledger.capture(1, 11_499, 1_500, "refuse")
    assert ledger.capture(1, 2, 1_500, "refuse")["status"] == "refused_tolerance"
    assert ledger.holds[1].captured_cents <= 11_500


def test_over_limit_capture_refuses_or_caps_by_policy():
    refusing = build()
    assert refusing.capture(1, 11_001, 1_000, "refuse") == {
        "status": "refused_tolerance",
        "accepted": 0,
        "refused": 11_001,
    }

    capping = build()
    outcome = capping.capture(1, 11_001, 1_000, "cap")
    assert outcome == {"status": "capped", "accepted": 11_000, "refused": 1}
    assert capping.total_captured == 11_000


def test_expired_hold_refuses_late_captures_and_releases_the_remainder():
    ledger = build()
    ledger.capture(1, 4_000, 0, "refuse")
    assert ledger.expire(2, 3) == 0
    assert ledger.expire(3, 3) == 11_000
    assert ledger.capture(1, 500, 0, "refuse")["status"] == "refused_expired"
    assert ledger.total_released == 11_000
    assert ledger.check_invariant()


def test_expiry_is_inclusive_of_the_final_day():
    ledger = build()
    assert ledger.expire(6, 7) == 0
    assert ledger.expire(7, 7) == 15_000
    assert ledger.open_cents == 0


def test_duplicate_authorisation_is_rejected():
    ledger = build()
    with pytest.raises(ValueError):
        ledger.authorise(1, 1_000, 3)
