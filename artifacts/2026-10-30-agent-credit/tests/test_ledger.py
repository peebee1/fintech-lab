import pytest

from creditnet.ledger import Ledger, Obligation


def ob(i: int, payer: str, payee: str, amount: int) -> Obligation:
    return Obligation(id=i, payer=payer, payee=payee, amount=amount, ts=i)


def test_self_payment_is_refused() -> None:
    with pytest.raises(ValueError, match="self payment"):
        ob(1, "a", "a", 100)


def test_non_positive_amount_is_refused() -> None:
    for amount in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            ob(1, "a", "b", amount)


def test_empty_ledger_has_no_positions() -> None:
    ledger = Ledger()
    assert ledger.net_positions() == {}
    assert ledger.gross_value() == 0
    assert ledger.imbalance() == 0
    assert ledger.members() == ()


def test_positions_sum_to_zero() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 500))
    ledger.add(ob(2, "b", "c", 300))
    ledger.add(ob(3, "c", "a", 700))
    positions = ledger.net_positions()
    assert positions == {"a": 200, "b": 200, "c": -400}
    assert ledger.imbalance() == 0
    assert ledger.gross_value() == 1500


def test_a_cycle_nets_to_zero() -> None:
    ledger = Ledger()
    for index, (payer, payee) in enumerate([("a", "b"), ("b", "c"), ("c", "a")]):
        ledger.add(ob(index, payer, payee, 1_000))
    assert set(ledger.net_positions().values()) == {0}
    assert ledger.gross_value() == 3_000


def test_outflow_and_inflow_are_not_netted() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 400))
    ledger.add(ob(2, "b", "a", 250))
    assert ledger.outflow("a") == 400
    assert ledger.inflow("a") == 250
    assert ledger.net_positions()["a"] == -150


def test_bilateral_keeps_direction() -> None:
    ledger = Ledger()
    ledger.add(ob(1, "a", "b", 400))
    ledger.add(ob(2, "b", "c", 100))
    assert ledger.bilateral() == {("a", "b"): 400, ("b", "c"): 100}
