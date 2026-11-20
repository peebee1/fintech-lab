from qualification.book import Transaction, failures
from qualification.card import (
    L3_THRESHOLD_CENTS,
    RULES,
    RULE_CODES,
    fee_cents,
    uplift_bp,
)


def tx(**overrides) -> Transaction:
    base = dict(
        id=1,
        day=0,
        amount_cents=10_000,
        product="consumer_credit",
        channel="card_present",
        authorized=True,
        avs_ok=True,
        cvv_ok=True,
        level2=True,
        level3=True,
        stored_credential=True,
        mcc_matched=True,
        same_day_batch=True,
    )
    base.update(overrides)
    return Transaction(**base)


def test_rules_are_ordered_by_uplift_so_precedence_is_well_defined():
    uplifts = [r.uplift_bp for r in RULES]
    assert uplifts == sorted(uplifts, reverse=True)
    assert len(set(uplifts)) == len(uplifts)
    assert RULE_CODES[0] == "unauthorized"


def test_fee_rounds_half_up_and_adds_the_fixed_component():
    # 175 bps of 100.00 is 1.75, plus 10 cents.
    assert fee_cents(10_000, "consumer_credit", None) == 185
    # 1 cent at 175 bps rounds to 0, the fixed part is still charged.
    assert fee_cents(1, "consumer_credit", None) == 10
    # A tier adds its uplift on the same base.
    assert fee_cents(10_000, "consumer_credit", "avs_cvv") == 240
    assert uplift_bp(None) == 0


def test_a_transaction_failing_two_rules_is_billed_at_the_higher_one():
    two = tx(product="commercial_credit", level2=False, same_day_batch=False)
    assert failures(two) == ("commercial_data", "late_batch")
    assert fee_cents(two.amount_cents, two.product, "commercial_data") > fee_cents(
        two.amount_cents, two.product, "late_batch"
    )
    assert failures(two)[0] == "commercial_data"


def test_level3_threshold_is_inclusive_and_only_for_commercial_cards():
    at = tx(product="commercial_credit", amount_cents=L3_THRESHOLD_CENTS, level3=False)
    below = tx(product="commercial_credit", amount_cents=L3_THRESHOLD_CENTS - 1, level3=False)
    consumer = tx(product="consumer_credit", amount_cents=L3_THRESHOLD_CENTS, level3=False)
    assert failures(at) == ("commercial_l3",)
    assert failures(below) == ()
    assert failures(consumer) == ()


def test_avs_rule_does_not_apply_to_card_present():
    present = tx(channel="card_present", avs_ok=False, cvv_ok=False)
    ecommerce = tx(channel="ecommerce", avs_ok=False, cvv_ok=True)
    recurring = tx(channel="recurring", stored_credential=False)
    assert failures(present) == ()
    assert failures(ecommerce) == ("avs_cvv",)
    assert failures(recurring) == ("stored_credential",)


def test_stored_credential_rule_needs_both_a_recurring_charge_and_a_missing_flag():
    assert failures(tx(channel="recurring", stored_credential=False)) == ("stored_credential",)
    assert failures(tx(channel="recurring", stored_credential=True)) == ()
    assert failures(tx(channel="ecommerce", stored_credential=False)) == ()


def test_clean_transaction_has_no_failures_and_the_cheapest_fee():
    clean = tx()
    assert failures(clean) == ()
    assert fee_cents(clean.amount_cents, clean.product, None) < fee_cents(
        clean.amount_cents, clean.product, "late_batch"
    )
