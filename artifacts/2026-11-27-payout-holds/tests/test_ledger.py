"""The ledger: exact arithmetic, the two identities, and the hand-checked cases."""

from payoutholds.book import Book, Order, Refund, Seller
from payoutholds.ledger import FUNDING_RATE, simulate, simulate_oracle
from payoutholds.policies import LADDER, Policy


def tiny_book(orders, refunds, exit_day=10, days=10):
    seller = Seller(id="s0000", band="established", join_day=0, exit_day=exit_day)
    return Book(seed=1, days=days, sellers=[seller], orders=orders, refunds=refunds)


def one_sale_book(refund_day=5, refund_cents=4_000, fee_cents=500):
    return tiny_book(
        [Order(id=1, seller_id="s0000", day=0, amount_cents=10_000)],
        [
            Refund(
                order_id=1,
                seller_id="s0000",
                sale_day=0,
                arrival_day=refund_day,
                amount_cents=refund_cents,
                fee_cents=fee_cents,
            )
        ],
    )


def two_sale_book():
    return tiny_book(
        [
            Order(id=1, seller_id="s0000", day=0, amount_cents=10_000),
            Order(id=2, seller_id="s0000", day=10, amount_cents=10_000),
        ],
        [
            Refund(
                order_id=1,
                seller_id="s0000",
                sale_day=0,
                arrival_day=5,
                amount_cents=4_000,
                fee_cents=500,
            )
        ],
        exit_day=20,
        days=20,
    )


def test_a_late_refund_with_no_reserve_is_a_write_off():
    result = simulate(Policy("pay_t1"), one_sale_book())
    totals = result["totals"]
    assert totals["paid"] == 10_000
    assert totals["written_off"] == 4_500
    assert totals["refund_cost"] == 4_500
    assert result["checks"]["sales_fully_allocated"]
    assert result["checks"]["refunds_fully_covered"]


def test_a_full_reserve_covers_the_refund_exactly():
    result = simulate(
        Policy("full_reserve", reserve_rate=1.0, reserve_days=30), one_sale_book()
    )
    totals = result["totals"]
    assert totals["written_off"] == 0
    assert totals["charged_held"] == 4_500
    assert totals["paid"] == 5_500
    # 4,500 held from day 0 to day 5, 5,500 from day 0 to day 31.
    assert totals["float_cents_days"] == 4_500 * 5 + 5_500 * 31


def test_float_cost_is_the_day_weighted_rate():
    result = simulate(Policy("reserve_10", reserve_rate=0.10, reserve_days=30), one_sale_book())
    totals = result["totals"]
    expected = round(totals["float_cents_days"] * FUNDING_RATE / 365)
    assert totals["float_cost_cents"] == expected


def test_clawback_recovers_the_debt_from_the_next_payout():
    result = simulate(Policy("pay_t1"), two_sale_book())
    totals = result["totals"]
    assert totals["written_off"] == 0
    assert totals["charged_carry"] == 4_500
    assert totals["paid"] == 15_500
    assert result["checks"]["sales_fully_allocated"]


def test_without_clawback_the_platform_pays_and_eats_it():
    result = simulate(Policy("no_clawback", clawback=False), two_sale_book())
    totals = result["totals"]
    assert totals["written_off"] == 4_500
    assert totals["paid"] == 20_000
    assert result["checks"]["refunds_fully_covered"]


def test_write_off_never_exceeds_the_refund_it_covers():
    for policy in LADDER:
        result = simulate(policy, one_sale_book())
        assert result["totals"]["written_off"] <= result["totals"]["refund_cost"]


def test_the_oracle_holds_exactly_the_late_refund():
    result = simulate_oracle(one_sale_book())
    totals = result["totals"]
    assert totals["written_off"] == 0
    assert totals["charged_held"] == 4_500
    assert totals["paid"] == 5_500
    assert totals["float_cents_days"] == 4_500 * 5


def test_the_oracle_floor_is_never_negative_and_writes_nothing_off(book):
    result = simulate_oracle(book)
    assert result["totals"]["written_off"] == 0
    assert result["checks"]["sales_fully_allocated"]
    assert result["checks"]["refunds_fully_covered"]


def test_every_policy_balances_on_the_real_book(book):
    for policy in LADDER:
        result = simulate(policy, book)
        assert all(result["checks"].values()), policy.name
        rows = result["rows"]
        for row in rows:
            assert row["sales"] == (
                row["paid"] + row["charged_held"] + row["charged_carry"]
            )
            assert row["refund_cost"] == (
                row["charged_held"] + row["charged_carry"] + row["written_off"]
            )


def test_zero_reserve_actually_loses_money(book):
    assert simulate(Policy("pay_t1"), book)["totals"]["written_off"] > 0


def test_the_reserve_is_what_reduces_the_loss(book):
    base = simulate(Policy("pay_t1"), book)["totals"]["written_off"]
    ten = simulate(Policy("reserve_10", reserve_rate=0.10, reserve_days=30), book)
    assert ten["totals"]["written_off"] < base
    assert ten["totals"]["charged_held"] > simulate(Policy("pay_t1"), book)["totals"]["charged_held"]


def test_a_reserve_below_one_cent_holds_nothing():
    """int() truncation is the floor: a rate this small is the same as zero."""
    policy = Policy("dust", reserve_rate=0.00001, reserve_days=30)
    result = simulate(policy, one_sale_book())
    assert result["totals"]["charged_held"] == 0
    assert result["totals"]["written_off"] == 4_500


def test_tiered_terms_split_on_band_and_tenure():
    policy = Policy("tiered_hold", tiered=True)
    assert policy.terms("established", 100) == (2, 0.0, 0)
    assert policy.terms("established", 30) == (14, 0.10, 60)
    assert policy.terms("new", 400) == (14, 0.10, 60)
    assert policy.terms("risky", 400) == (14, 0.10, 60)
    reserve_only = Policy("tiered_reserve", tiered=True, tier_variant="reserve_only")
    assert reserve_only.terms("new", 30) == (1, 0.20, 60)


def test_a_policy_that_pays_instantly_has_no_float_cost():
    result = simulate(Policy("same_day", hold_days=0), one_sale_book())
    assert result["totals"]["float_cents_days"] == 0
    assert result["totals"]["float_cost_cents"] == 0
