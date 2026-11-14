"""The rules that make an append only journal worth more than a table of numbers."""

from datetime import date

import pytest

from ledgerclose.entry import Line
from ledgerclose.ledger import Ledger, Refusal


def pair(amount=100_000, debit="cash", credit="fee_revenue"):
    return [Line(debit, amount), Line(credit, -amount)]


def test_unbalanced_and_empty_postings_are_refused(ledger):
    with pytest.raises(Refusal) as unbalanced:
        ledger.post([Line("cash", 500_000), Line("fee_revenue", -400_000)], date(2026, 1, 5))
    assert unbalanced.value.rule == "Unbalanced"
    with pytest.raises(Refusal) as empty:
        ledger.post([Line("cash", 0), Line("fee_revenue", 0)], date(2026, 1, 5))
    assert empty.value.rule == "EmptyPosting"
    assert len(ledger.journal) == 0


def test_write_into_a_closed_period_is_refused(ledger):
    ledger.post(pair(), date(2026, 1, 5))
    ledger.close("2026-01")
    with pytest.raises(Refusal) as caught:
        ledger.post(pair(), date(2026, 1, 20))
    assert caught.value.rule == "ClosedPeriod"
    assert len(ledger.journal) == 1


def test_idempotent_replay_returns_the_original_entry(ledger):
    first = ledger.post(pair(250_000), date(2026, 1, 5), idempotency_key="txn-1")
    again = ledger.post(pair(999_000), date(2026, 1, 5), idempotency_key="txn-1")
    assert again.hash == first.hash
    assert len(ledger.journal) == 1


def test_amend_is_refused(ledger):
    entry = ledger.post(pair(), date(2026, 1, 5))
    with pytest.raises(Refusal) as caught:
        ledger.amend(entry.entry_id, pair(1))
    assert caught.value.rule == "NoAmend"


def test_every_reversal_guard_fires(ledger):
    entry = ledger.post(pair(100_000), date(2026, 1, 5))
    with pytest.raises(Refusal) as missing:
        ledger.reverse("e999999")
    assert missing.value.rule == "ReversalOfMissing"
    with pytest.raises(Refusal) as inexact:
        ledger.post(pair(90_000), date(2026, 1, 6), reverses=entry.entry_id)
    assert inexact.value.rule == "ReversalNotExact"
    with pytest.raises(Refusal) as backwards:
        ledger.reverse(entry.entry_id, date(2026, 1, 4))
    assert backwards.value.rule == "ReversalBeforeOriginal"
    ledger.reverse(entry.entry_id, date(2026, 1, 6))
    with pytest.raises(Refusal) as twice:
        ledger.reverse(entry.entry_id, date(2026, 1, 7))
    assert twice.value.rule == "AlreadyReversed"
    assert ledger.control_totals("2026-01") == {}


def test_reversal_of_a_wrong_sign_plan_is_not_the_exact_inverse(ledger):
    entry = ledger.post([Line("cash", 100_000), Line("fee_revenue", -100_000)], date(2026, 1, 5))
    with pytest.raises(Refusal) as caught:
        ledger.post([Line("cash", -100_000), Line("merchant_payable", 100_000)], date(2026, 1, 6), reverses=entry.entry_id)
    assert caught.value.rule == "ReversalNotExact"


def test_balances_are_derived_and_equal_an_independent_fold(ledger):
    posted = [pair(120_000), pair(80_000, "cash", "merchant_payable")]
    for lines in posted:
        ledger.post(lines, date(2026, 1, 5))
    expected: dict[str, int] = {}
    for lines in posted:
        for line in lines:
            expected[line.account] = expected.get(line.account, 0) + line.amount_minor
    assert ledger.balances() == expected
    assert sum(expected.values()) == 0


def test_balances_cannot_be_mutated_by_a_caller(ledger):
    ledger.post(pair(), date(2026, 1, 5))
    view = ledger.balances()
    view["cash"] = 123
    assert ledger.balances()["cash"] == 100_000


def test_balances_respect_as_of(ledger):
    ledger.post(pair(100_000), date(2026, 1, 5))
    ledger.post(pair(50_000), date(2026, 2, 5))
    assert ledger.balances(as_of=date(2026, 1, 31))["cash"] == 100_000
    assert ledger.balances(as_of=date(2026, 2, 28))["cash"] == 150_000


def test_trial_balance_is_balanced_and_nets_to_zero(ledger):
    ledger.post(pair(100_000), date(2026, 1, 5))
    ledger.post([Line("cash", 40_000), Line("merchant_payable", -40_000)], date(2026, 1, 9))
    trial = ledger.trial_balance("2026-01")
    assert trial.balanced
    assert trial.total_debit_minor == trial.total_credit_minor == 140_000
    assert trial.net_minor == 0
    assert {row.account: row.net_minor for row in trial.rows} == ledger.control_totals("2026-01")


def test_journal_survives_a_reopen(tmp_path, clock):
    path = tmp_path / "journal"
    ledger = Ledger(path, clock=clock)
    for index in range(5):
        ledger.post(pair(10_000 + index), date(2026, 1, 5 + index))
    reopened = Ledger(path, clock=clock)
    assert [entry.hash for entry in reopened.journal] == [entry.hash for entry in ledger.journal]
    assert reopened.balances() == ledger.balances()
    assert reopened.verify().ok
