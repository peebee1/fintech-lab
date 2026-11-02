import json
from pathlib import Path

import pytest

from idemconform.ledger import HandlerError, Ledger
from idemconform.store import COMMITTED, IN_FLIGHT, JsonFileStore, MemoryStore, Record

BODY = {"account": "acct_a", "amount": 1250, "currency": "eur", "customer": "cus_1"}


def test_ledger_refuses_zero_and_negative_amounts():
    ledger = Ledger()
    for bad in (0, -1):
        with pytest.raises(ValueError):
            ledger.append("acct_a", "k", bad, "EUR", "cus_1")
    assert len(ledger) == 0


def test_ledger_refuses_a_float_amount():
    with pytest.raises(ValueError):
        Ledger().append("acct_a", "k", 12.5, "EUR", "cus_1")


def test_ledger_charge_ids_are_sequential_and_stable():
    ledger = Ledger()
    first = ledger.append("acct_a", "k1", 100, "EUR", "cus_1")
    second = ledger.append("acct_a", "k2", 200, "EUR", "cus_1")
    assert (first.charge_id, second.charge_id) == ("ch_0001", "ch_0002")
    assert ledger.total() == 300


def test_ledger_find_is_scoped_when_asked():
    ledger = Ledger()
    ledger.append("acct_a", "shared", 100, "EUR", "cus_1")
    ledger.append("acct_b", "shared", 200, "EUR", "cus_1")
    assert ledger.find("acct_a", "shared").amount == 100
    assert ledger.find("acct_b", "shared").amount == 200
    assert ledger.find(None, "shared").amount == 100


def test_fail_next_append_raises_once_then_recovers():
    ledger = Ledger()
    ledger.fail_next_append()
    with pytest.raises(HandlerError):
        ledger.append("acct_a", "k", 100, "EUR", "cus_1")
    assert len(ledger) == 0
    ledger.append("acct_a", "k", 100, "EUR", "cus_1")
    assert len(ledger) == 1


def test_store_returns_a_copy_so_callers_cannot_corrupt_state():
    store = MemoryStore()
    store.put(Record("acct_a", "k", "fp", COMMITTED, 0, 0, "owner", {"status": 201, "body": {"charge_id": "ch_1"}}))
    taken = store.get("acct_a", "k")
    taken.state = IN_FLIGHT
    taken.response["status"] = 500
    fresh = store.get("acct_a", "k")
    assert fresh.state == COMMITTED
    assert fresh.response["status"] == 201


def test_unscoped_store_collides_across_accounts():
    store = MemoryStore(scoped=False)
    store.put(Record("acct_a", "k", "fp", COMMITTED, 0, 0, "o", {"status": 201, "body": {}}))
    assert store.get("acct_b", "k") is not None


def test_scoped_store_does_not_collide():
    store = MemoryStore(scoped=True)
    store.put(Record("acct_a", "k", "fp", COMMITTED, 0, 0, "o", {"status": 201, "body": {}}))
    assert store.get("acct_b", "k") is None


def test_json_store_survives_reopen(tmp_path: Path):
    path = tmp_path / "idem.json"
    first = JsonFileStore(path)
    first.put(Record("acct_a", "k", "fp", COMMITTED, 0, 0, "o", {"status": 201, "body": {"charge_id": "ch_1"}}))
    second = JsonFileStore(path)
    record = second.get("acct_a", "k")
    assert record is not None
    assert record.response["body"]["charge_id"] == "ch_1"


def test_json_store_refuses_a_scoping_mismatch(tmp_path: Path):
    path = tmp_path / "idem.json"
    JsonFileStore(path, scoped=True).put(Record("acct_a", "k", "fp", COMMITTED, 0, 0, "o", None))
    with pytest.raises(ValueError):
        JsonFileStore(path, scoped=False)


def test_json_store_delete_is_persisted(tmp_path: Path):
    path = tmp_path / "idem.json"
    store = JsonFileStore(path)
    store.put(Record("acct_a", "k", "fp", IN_FLIGHT, 0, 30, "o", None))
    store.delete("acct_a", "k")
    assert JsonFileStore(path).get("acct_a", "k") is None
    assert json.loads(path.read_text())["records"] == []
