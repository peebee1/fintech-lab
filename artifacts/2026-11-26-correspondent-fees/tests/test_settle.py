"""The replay: the ledger has to add up, and each code has one job."""

import pytest

from corrfee.book import Book, Corridor, Hop, Invoice
from corrfee.fees import our_fee, priced, sender_bank_fee, sha_fee
from corrfee.policies import Policy
from corrfee.settle import (
    CLAIM_OPS_CENTS,
    TOLERANCE_BPS,
    TOLERANCE_MIN_CENTS,
    apply_code,
    settle,
    tolerance_for,
)


def one_invoice(amount: int = 1_000_000, hop_fee: int = 3_000) -> Book:
    invoice = Invoice(
        id="INV-1",
        day=0,
        corridor="US-MX",
        hops_count=1,
        currency="MXN",
        amount_cents=amount,
        hops=(Hop(index=1, bank="hop-1", fee_cents=hop_fee),),
        receiver_fee_cents=0,
    )
    corridor = Corridor("US-MX", "US", "MX", "MXN", 1, 1.0)
    return Book(seed=0, days=1, invoices=(invoice,), corridors=(corridor,))


def policy(name: str, code: str, repair: str = "never", threshold: int = 0) -> Policy:
    return Policy(name, code, repair, threshold)


# ---------------------------------------------------------------- fees


def test_a_fee_is_floored_and_capped():
    assert sha_fee(1_000) == 1_000, "the floor holds a tiny ticket"
    assert priced(1, 8, 1_000, 6_000) == 1_000
    assert priced(10_000_000, 8, 1_000, 6_000) == 6_000
    assert priced(5_000_000, 8, 1_000, 6_000) == 4_000


def test_a_fee_never_rounds_down():
    assert priced(10_001, 8, 0, 100_000) == 9


def test_the_bundled_charge_is_the_expensive_one_at_this_size():
    assert our_fee(1_000_000) > sha_fee(1_000_000)
    assert sha_fee(1_000_000) == sender_bank_fee(1_000_000)


# ---------------------------------------------------------------- codes


def test_our_delivers_the_instructed_amount():
    book = one_invoice()
    fee, deductions, delivered = apply_code("OUR", book.invoices[0])
    assert delivered == 1_000_000
    assert deductions == 0
    assert fee == 3_500


def test_sha_takes_the_chain_off_the_amount():
    book = one_invoice()
    fee, deductions, delivered = apply_code("SHA", book.invoices[0])
    assert fee == 1_000
    assert deductions == 3_000
    assert delivered == 997_000


def test_ben_also_takes_the_sender_bank_fee_off_the_amount():
    book = one_invoice()
    fee, deductions, delivered = apply_code("BEN", book.invoices[0])
    assert fee == 0
    assert deductions == 3_000 + 1_000
    assert delivered == 1_000_000 - 4_000


# ---------------------------------------------------------------- claims


def test_the_tolerance_is_a_floor_or_a_share():
    assert tolerance_for(100_000, TOLERANCE_BPS, TOLERANCE_MIN_CENTS) == TOLERANCE_MIN_CENTS
    assert tolerance_for(10_000_000, TOLERANCE_BPS, TOLERANCE_MIN_CENTS) == 5_000


def test_a_shortfall_above_tolerance_raises_a_claim_and_does_not_repair_itself():
    result = settle(one_invoice(), policy("sha_none", "SHA"))
    row = result.rows[0]
    assert row.claimed is True
    assert row.repaired is False
    assert row.supplier_cents == 3_000
    assert row.sender_outlay_cents == 1_000 + CLAIM_OPS_CENTS


def test_repairing_adds_the_wire_fee_and_the_desk_to_the_same_money():
    result = settle(one_invoice(), policy("sha_repair_all", "SHA", "claims"))
    row = result.rows[0]
    assert row.repaired is True
    assert row.repair_fee_cents == 3_500, "the minimum wire beats a USD 30 shortfall"
    assert row.sender_outlay_cents == 1_000 + 3_000 + 3_500 + CLAIM_OPS_CENTS
    assert row.supplier_cents == 0


def test_a_shortfall_inside_tolerance_is_absorbed_without_a_claim():
    result = settle(one_invoice(hop_fee=1_000), policy("sha_none", "SHA"))
    row = result.rows[0]
    assert row.claimed is False
    assert row.ops_cents == 0
    assert row.supplier_cents == 1_000


def test_the_threshold_decides_and_the_claim_decides():
    policy_50 = policy("sha_claim_50", "SHA", "above", 5_000)
    assert policy_50.wants_repair(5_000) is False
    assert policy_50.wants_repair(5_001) is True


# ---------------------------------------------------------------- ledger


@pytest.mark.parametrize("name,code,repair,threshold", [
    ("ben", "BEN", "never", 0),
    ("sha", "SHA", "never", 0),
    ("our", "OUR", "never", 0),
    ("repair", "SHA", "claims", 0),
    ("claim_50", "SHA", "above", 5_000),
])
def test_every_row_conserves_value(book, name, code, repair, threshold):
    result = settle(book, policy(name, code, repair, threshold))
    for row in result.rows:
        assert row.delivered_cents + row.shortfall_cents == row.amount_cents
        assert row.sender_outlay_cents == (
            row.sender_fee_cents
            + (row.shortfall_cents if row.repaired else 0)
            + row.repair_fee_cents
            + row.ops_cents
        )
        assert row.economic_cents == row.sender_outlay_cents + row.supplier_cents


def test_the_book_totals_partition(book):
    result = settle(book, policy("sha", "SHA"))
    assert result.delivered_cents + result.shortfall_cents == result.value_cents
    assert (
        result.sender_total_cents
        == result.sender_fee_cents + result.repair_cents + result.repair_fee_cents + result.ops_cents
    )
    assert result.economic_cents == result.sender_total_cents + result.supplier_cents


def test_our_raises_no_claim_at_all(book):
    result = settle(book, policy("our", "OUR"))
    assert result.claims == 0
    assert result.shortfall_cents == 0
    assert result.supplier_cents == 0


def test_ben_and_sha_leave_the_same_hole_in_the_amount(book):
    sha = settle(book, policy("sha", "SHA"))
    ben = settle(book, policy("ben", "BEN"))
    assert ben.economic_cents - sha.economic_cents == ben.ops_cents - sha.ops_cents


def test_the_replay_is_deterministic(book):
    a = settle(book, policy("sha", "SHA"))
    b = settle(book, policy("sha", "SHA"))
    assert [row.shortfall_cents for row in a.rows] == [row.shortfall_cents for row in b.rows]
    assert a.economic_cents == b.economic_cents
