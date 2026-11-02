import pytest

from idemconform.api import PaymentAPI, fingerprint, normalize

BODY = {"account": "acct_a", "amount": 1250, "currency": "eur", "customer": "cus_1"}


def test_normalize_uppercases_currency_and_keeps_minor_units():
    assert normalize(BODY)["currency"] == "EUR"
    assert normalize(BODY)["amount"] == 1250


@pytest.mark.parametrize("bad", [0, -5, 12.5, "1250", True, None])
def test_normalize_refuses_a_bad_amount(bad):
    with pytest.raises(ValueError):
        normalize({"amount": bad, "currency": "EUR"})


def test_fingerprint_ignores_key_order_and_currency_case():
    reordered = {"customer": "cus_1", "currency": "EUR", "amount": 1250, "account": "acct_a"}
    assert fingerprint(BODY) == fingerprint(reordered)


def test_fingerprint_changes_with_amount():
    assert fingerprint(BODY) != fingerprint({**BODY, "amount": 1251})


def test_fingerprint_ignores_the_account_because_the_account_is_the_namespace():
    other = {**BODY, "account": "acct_b"}
    assert fingerprint(BODY) == fingerprint(other)


def test_reserve_replays_the_same_body():
    api = PaymentAPI("reserve")
    first = api.request("acct_a", "k", BODY, now=0)
    second = api.request("acct_a", "k", BODY, now=1)
    assert first.status == second.status == 201
    assert second.replayed and not second.executed
    assert first.canonical_body() == second.canonical_body()
    assert len(api.ledger) == 1


def test_reserve_conflicts_on_a_changed_body():
    api = PaymentAPI("reserve")
    api.request("acct_a", "k", BODY, now=0)
    conflict = api.request("acct_a", "k", {**BODY, "amount": 999}, now=1)
    assert conflict.status == 422
    assert conflict.body["error"] == "idempotency_key_reuse"
    assert len(api.ledger) == 1


def test_reserve_blocks_a_second_owner_while_the_lease_runs():
    api = PaymentAPI("reserve")
    held = api.admit("acct_a", "k", BODY, now=0, owner="a")
    blocked = api.request("acct_a", "k", BODY, now=1, owner="b")
    assert blocked.status == 409
    assert blocked.headers()["Retry-After"] == "29"
    api.finish(held)
    assert len(api.ledger) == 1


def test_reserve_releases_a_stale_claim_with_no_effect():
    api = PaymentAPI("reserve")
    api.crash_before_effect("acct_a", "k", BODY, now=0)
    survivor = api.reopen()
    retry = survivor.request("acct_a", "k", BODY, now=31)
    assert retry.status == 201
    assert len(survivor.ledger) == 1


def test_reserve_recovers_a_charge_written_before_the_response():
    api = PaymentAPI("reserve")
    crash = api.crash_after_effect("acct_a", "k", BODY, now=0)
    survivor = api.reopen()
    replay = survivor.request("acct_a", "k", BODY, now=31)
    assert replay.status == 201
    assert replay.replayed
    assert replay.body["charge_id"] == crash["charge_id"]
    assert len(survivor.ledger) == 1


def test_reserve_recovers_from_a_json_store_reopened_from_disk(tmp_path):
    from idemconform.api import fresh_file_api

    path = tmp_path / "idem.json"
    api = fresh_file_api("reserve", path)
    crash = api.crash_after_effect("acct_a", "k", BODY, now=0)
    survivor = fresh_file_api("reserve", path)
    replay = survivor.request("acct_a", "k", BODY, now=31)
    assert replay.replayed
    assert replay.body["charge_id"] == crash["charge_id"]
    assert len(survivor.ledger) == 1


def test_reserve_refuses_an_expired_key_instead_of_rerunning():
    api = PaymentAPI("reserve")
    api.request("acct_a", "k", BODY, now=0)
    late = api.request("acct_a", "k", BODY, now=90_000)
    assert late.status == 409
    assert late.body["error"] == "idempotency_key_expired"
    assert len(api.ledger) == 1


def test_reserve_releases_the_key_when_the_processor_fails():
    api = PaymentAPI("reserve")
    api.ledger.fail_next_append()
    failed = api.request("acct_a", "k", BODY, now=0)
    assert failed.status == 502
    retry = api.request("acct_a", "k", BODY, now=1)
    assert retry.status == 201 and retry.executed
    assert len(api.ledger) == 1


def test_error_cached_implementation_traps_the_retry():
    api = PaymentAPI("error_cached")
    api.ledger.fail_next_append()
    assert api.request("acct_a", "k", BODY, now=0).status == 502
    retry = api.request("acct_a", "k", BODY, now=1)
    assert retry.status == 502 and retry.replayed


def test_store_after_double_charges_under_overlap():
    """This is the defect the suite exists to catch, pinned as behaviour."""
    api = PaymentAPI("store_after")
    first = api.admit("acct_a", "k", BODY, now=0, owner="a")
    second = api.admit("acct_a", "k", BODY, now=0, owner="b")
    api.finish(first)
    api.finish(second)
    assert len(api.ledger) == 2


def test_naive_ignores_the_key():
    api = PaymentAPI("naive")
    api.request("acct_a", "k", BODY, now=0)
    api.request("acct_a", "k", BODY, now=0)
    assert len(api.ledger) == 2


def test_global_key_collides_across_accounts():
    api = PaymentAPI("global_key")
    first = api.request("acct_a", "shared", BODY, now=0)
    second = api.request("acct_b", "shared", {**BODY, "account": "acct_b"}, now=1)
    assert second.replayed
    assert second.body["account"] == "acct_a"
    assert second.body["charge_id"] == first.body["charge_id"]
    assert len(api.ledger) == 1


def test_a_missing_key_is_refused_by_every_implementation_that_claims_one():
    for mode in ("global_key", "store_after", "error_cached", "reserve"):
        api = PaymentAPI(mode)
        assert api.request("acct_a", "", BODY, now=0).status == 400
        assert len(api.ledger) == 0


def test_two_identical_runs_produce_identical_bytes():
    def run():
        api = PaymentAPI("reserve")
        return [api.request("acct_a", "k", BODY, now=i).canonical_body() for i in (0, 1, 2)]

    assert run() == run()
