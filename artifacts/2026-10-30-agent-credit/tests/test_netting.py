from creditnet.ledger import Ledger, Obligation
from creditnet.netting import (
    bilateral_settlement_value,
    reduction,
    settlement,
    settlement_value,
)


def ob(i: int, payer: str, payee: str, amount: int) -> Obligation:
    return Obligation(id=i, payer=payer, payee=payee, amount=amount, ts=i)


def test_empty_ledger_settles_nothing() -> None:
    assert settlement(Ledger()) == ()
    assert settlement_value(Ledger()) == 0
    assert reduction(Ledger()) == 0.0


def test_single_obligation_settles_in_full() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 900))
    orders = settlement(ledger)
    assert len(orders) == 1
    assert orders[0].payer == "a"
    assert orders[0].payee == "b"
    assert orders[0].amount == 900
    assert settlement_value(ledger) == 900
    assert reduction(ledger) == 0.0


def test_cycle_settles_to_zero_but_is_not_free() -> None:
    ledger = Ledger()
    for index, (payer, payee) in enumerate([("a", "b"), ("b", "c"), ("c", "a")]):
        ledger.add(ob(index, payer, payee, 1_000))
    assert settlement(ledger) == ()
    assert settlement_value(ledger) == 0
    assert reduction(ledger) == 1.0


def test_instructions_conserve_value() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 300))
    ledger.add(ob(2, "b", "c", 500))
    ledger.add(ob(3, "c", "a", 100))
    orders = settlement(ledger)
    positions = ledger.net_positions()
    paid = {}
    received = {}
    for order in orders:
        paid[order.payer] = paid.get(order.payer, 0) + order.amount
        received[order.payee] = received.get(order.payee, 0) + order.amount
    for member, position in positions.items():
        assert received.get(member, 0) - paid.get(member, 0) == position
    assert sum(paid.values()) == sum(received.values()) == settlement_value(ledger)


def test_bilateral_sits_between_gross_and_multilateral() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 1_000))
    ledger.add(ob(2, "b", "a", 800))
    ledger.add(ob(3, "b", "c", 500))
    gross = ledger.gross_value()
    bilateral = bilateral_settlement_value(ledger)
    multilateral = settlement_value(ledger)
    assert 0 <= multilateral <= bilateral <= gross
    assert bilateral == 700  # |1000 - 800| plus the one way 500
    assert multilateral == 500  # a pays 200 and b pays 300 to clear both pairs at once


def test_reduction_stays_a_fraction() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 1_000))
    ledger.add(ob(2, "b", "a", 400))
    assert 0.0 <= reduction(ledger) < 1.0
    assert reduction(ledger) == 1 - 600 / 1400
