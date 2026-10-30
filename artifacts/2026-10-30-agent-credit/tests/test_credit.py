import pytest

from creditnet.credit import GROSS, NET, RULES, UNLIMITED, CreditBook
from creditnet.ledger import Obligation


def ob(i: int, payer: str, payee: str, amount: int) -> Obligation:
    return Obligation(id=i, payer=payer, payee=payee, amount=amount, ts=i)


def book(rule: str, limit: int = 100) -> CreditBook:
    return CreditBook({"router": limit, "a": limit, "b": limit}, rule)


def test_unknown_rule_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown rule"):
        CreditBook({"a": 100}, "vibes")


def test_non_positive_limit_is_refused() -> None:
    with pytest.raises(ValueError, match="positive"):
        CreditBook({"a": 0}, UNLIMITED)


def test_unknown_member_is_refused() -> None:
    with pytest.raises(KeyError, match="unknown payer"):
        book(UNLIMITED).admit(ob(1, "ghost", "a", 10))
    with pytest.raises(KeyError, match="unknown payee"):
        book(UNLIMITED).admit(ob(1, "a", "ghost", 10))


def test_unlimited_admits_everything() -> None:
    current = book(UNLIMITED, limit=1)
    assert current.admit(ob(1, "router", "a", 10_000))
    assert current.rejected == []
    assert current.max_net_debit() == 10_000


def test_gross_cap_refuses_a_flat_position() -> None:
    """The router sends 180 in total but is owed 90: gross sees 180, net sees 90."""
    current = book(GROSS)
    assert current.admit(ob(1, "router", "a", 90))
    assert current.admit(ob(2, "a", "router", 90))
    assert not current.admit(ob(3, "router", "b", 90))
    assert len(current.rejected) == 1
    assert current.admitted_value() == 180


def test_net_cap_admits_the_same_flat_position() -> None:
    current = book(NET)
    assert current.admit(ob(1, "router", "a", 90))
    assert current.admit(ob(2, "a", "router", 90))
    assert current.admit(ob(3, "router", "b", 90))
    assert current.rejected == []
    assert current.max_net_debit() == 90


def test_net_cap_refuses_a_real_debit() -> None:
    current = book(NET)
    assert current.admit(ob(1, "a", "b", 100))
    assert not current.admit(ob(2, "a", "b", 1))
    assert current.rejected_value() == 1


def test_inflow_earlier_in_the_window_funds_later_outflow() -> None:
    current = book(NET)
    assert current.admit(ob(1, "b", "a", 90))
    assert current.admit(ob(2, "a", "b", 90))
    assert current.projected_net_debit("a", 90) == 90
    assert current.ledger.imbalance() == 0


def test_limit_is_inclusive() -> None:
    current = book(NET)
    assert current.admit(ob(1, "a", "b", 100))
    assert not current.admit(ob(2, "a", "b", 1))


def test_rejected_obligations_never_enter_the_ledger() -> None:
    current = book(GROSS)
    current.admit(ob(1, "a", "b", 100))
    current.admit(ob(2, "a", "b", 1))
    assert len(current.ledger) == 1
    assert current.ledger.gross_value() == 100
    assert current.ledger.net_positions()["a"] == -100


def test_rules_are_the_three_names() -> None:
    assert RULES == (UNLIMITED, GROSS, NET)
