"""The hash is the identity of the fact, so it must not depend on how the lines arrived."""

from datetime import date, datetime, timezone

from ledgerclose.entry import GENESIS, Entry, Line, from_record, normalise, recompute, seal, to_record

NOW = datetime(2026, 5, 20, 9, 30, tzinfo=timezone.utc)


def make(lines, seq=1, prev=GENESIS):
    entry = Entry(
        entry_id="e000001",
        business_date=date(2026, 1, 5),
        posted_at=NOW,
        lines=normalise(lines),
    )
    return seal(entry, seq, prev)


def test_line_order_does_not_change_the_hash():
    a = make([Line("cash", 100), Line("fee_revenue", -100)])
    b = make([Line("fee_revenue", -100), Line("cash", 100)])
    assert a.hash == b.hash
    assert recompute(a) == a.hash


def test_amount_change_changes_the_hash():
    a = make([Line("cash", 100), Line("fee_revenue", -100)])
    b = make([Line("cash", 101), Line("fee_revenue", -101)])
    assert a.hash != b.hash


def test_prev_hash_is_inside_the_hash():
    lines = [Line("cash", 100), Line("fee_revenue", -100)]
    first = make(lines, seq=1, prev=GENESIS)
    second = make(lines, seq=2, prev=first.hash)
    third = make(lines, seq=2, prev=GENESIS)
    assert second.hash != third.hash


def test_record_round_trip_preserves_the_hash():
    entry = make([Line("cash", 100), Line("fee_revenue", -100)])
    restored = from_record(to_record(entry))
    assert restored == entry
    assert recompute(restored) == restored.hash
