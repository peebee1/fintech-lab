from mandate.rails import (
    NOTICE_SHORT,
    POST_REVOCATION,
    RAILS,
    get,
    violation_reasons,
)


def test_three_rails_with_different_notice_windows():
    assert set(RAILS) == {"card", "sepa", "upi"}
    assert get("card").prenotify_days == 0
    assert get("sepa").prenotify_days == 14
    assert get("upi").prenotify_days == 1


def test_afa_ceiling_is_inclusive():
    upi = get("upi")
    assert upi.needs_afa(1_500_000) is False
    assert upi.needs_afa(1_500_001) is True
    assert get("card").needs_afa(10_000_000) is False


def test_first_day_waits_for_the_notice_window():
    sepa = get("sepa")
    # Billed 20 days early, so the notice window has already run.
    assert sepa.first_day(due_day=30, issued_day=10) == 30
    # Billed on the day it is due, so the collection slips 14 days.
    assert sepa.first_day(due_day=30, issued_day=30) == 44
    # Card has no window at all.
    assert get("card").first_day(due_day=30, issued_day=30) == 30


def test_retry_lead_only_where_a_retry_is_a_new_collection():
    assert get("sepa").retry_lead() == 14
    assert get("upi").retry_lead() == 1
    assert get("card").retry_lead() == 0


def test_notice_violation_is_off_by_one():
    card = get("card")
    assert violation_reasons(card, 10, 10, None, None) == ()
    sepa = get("sepa")
    assert violation_reasons(sepa, 24, 10, None, None) == ()
    assert violation_reasons(sepa, 23, 10, None, None) == (NOTICE_SHORT,)


def test_revocation_gap_is_the_window_not_the_whole_future():
    sepa = get("sepa")
    # Asked to stop on day 20, rail stops it on day 21.
    assert violation_reasons(sepa, 20, 6, 20, 21) == (POST_REVOCATION,)
    # After the rail has stopped it, the issuer refuses the debit, so there is
    # nothing to claw back.
    assert violation_reasons(sepa, 21, 6, 20, 21) == ()
