"""A close is only worth something if it can fail.

The tests here prove the record reproduces, and that it stops reproducing when a fact behind
it changes on disk, without the ledger being asked.
"""

import json
from dataclasses import replace
from datetime import date

import pytest

from ledgerclose.entry import Line
from ledgerclose.ledger import Ledger, Refusal


def pair(amount=100_000):
    return [Line("cash", amount), Line("fee_revenue", -amount)]


def seed_january(ledger):
    ledger.post(pair(100_000), date(2026, 1, 5), idempotency_key="a")
    ledger.post(pair(60_000), date(2026, 1, 9), idempotency_key="b")
    ledger.post(pair(40_000), date(2026, 1, 12), idempotency_key="c")
    return ledger.close("2026-01")


def test_close_guards(ledger):
    ledger.post(pair(), date(2026, 1, 5))
    ledger.post(pair(), date(2026, 3, 5))
    with pytest.raises(Refusal) as out_of_order:
        ledger.close("2026-03")
    assert out_of_order.value.rule == "OutOfOrderClose"
    assert "2026-01" in out_of_order.value.detail
    with pytest.raises(Refusal) as bad_period:
        ledger.close("2026-13")
    assert bad_period.value.rule == "BadPeriod"
    ledger.close("2026-01")
    with pytest.raises(Refusal) as twice:
        ledger.close("2026-01")
    assert twice.value.rule == "AlreadyClosed"


def test_close_reproduces_from_a_fresh_read(tmp_path, clock):
    path = tmp_path / "journal"
    record = seed_january(Ledger(path, clock=clock))
    reopened = Ledger(path, clock=clock)
    stored = reopened.close_record("2026-01")
    assert stored is not None and stored.digest == record.digest
    check = reopened.verify_close(stored)
    assert check.ok and check.reason == "close reproduces"
    assert check.recomputed == check.recorded == record.control_totals
    assert reopened.drift("2026-01") == {}


def test_close_record_must_match_its_own_digest(ledger):
    record = seed_january(ledger)
    edited = replace(record, control_totals={**record.control_totals, "cash": 1})
    assert not ledger.verify_close(edited).ok


def test_close_refuses_a_backdated_fee_and_the_number_stays(ledger):
    record = seed_january(ledger)
    with pytest.raises(Refusal) as caught:
        ledger.post([Line("bank_fees", 185_000), Line("cash", -185_000)], date(2026, 1, 31))
    assert caught.value.rule == "ClosedPeriod"
    assert ledger.drift("2026-01") == {}
    assert ledger.control_totals("2026-01") == record.control_totals


def test_later_appends_do_not_disturb_a_signed_close(ledger):
    record = seed_january(ledger)
    ledger.post(pair(25_000), date(2026, 2, 3))
    assert ledger.verify_close(record).ok
    assert ledger.drift("2026-01") == {}


def test_out_of_band_edit_breaks_the_chain_and_exactly_one_close(tmp_path, clock):
    path = tmp_path / "journal"
    ledger = Ledger(path, clock=clock)
    seed_january(ledger)
    ledger.post(pair(30_000), date(2026, 2, 4))
    ledger.close("2026-02")
    assert sum(1 for check in ledger.verify_all_closes() if check.ok) == 2

    journal = path / "entries.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["lines"] = [
        [account, amount + 2_500_000] if account == "fee_revenue" else [account, amount]
        for account, amount in record["lines"]
    ]
    lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tampered = Ledger(path, clock=clock)
    chain = tampered.verify()
    assert not chain.ok and chain.broken_seq == 1 and chain.checked == 0
    assert "contents changed" in chain.reason
    assert [check.period for check in tampered.verify_all_closes() if not check.ok] == ["2026-01"]
    assert tampered.drift("2026-01")["fee_revenue"] == 2_500_000


def test_chain_break_is_reported_at_the_first_bad_entry(tmp_path, clock):
    path = tmp_path / "journal"
    seed_january(Ledger(path, clock=clock))
    journal = path / "entries.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["business_date"] = "2026-01-11"
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    chain = Ledger(path, clock=clock).verify()
    assert not chain.ok and chain.broken_seq == 2 and chain.checked == 1


def test_period_nets_sum_to_the_balance_movement(ledger):
    """Two independently computed values: period movements versus the balance at two dates."""
    seed_january(ledger)
    ledger.post(pair(45_000), date(2026, 2, 6))
    movement: dict[str, int] = {}
    for period in ("2026-01", "2026-02"):
        for account, amount in ledger.control_totals(period).items():
            movement[account] = movement.get(account, 0) + amount
    opening = ledger.balances(as_of=date(2025, 12, 31))
    closing = ledger.balances(as_of=date(2026, 2, 28))
    for account in set(movement) | set(closing):
        assert closing.get(account, 0) - opening.get(account, 0) == movement.get(account, 0)
