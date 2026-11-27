"""The book: deterministic, internally consistent, and plausible for a marketplace."""

from collections import Counter

from payoutholds.book import BAND_PARAMS, MAX_REFUND_LAG, generate


def test_same_seed_same_book():
    first = generate(seed=7, sellers=60, days=40)
    second = generate(seed=7, sellers=60, days=40)
    assert first.digest() == second.digest()


def test_a_different_seed_is_a_different_book():
    first = generate(seed=7, sellers=60, days=40)
    second = generate(seed=8, sellers=60, days=40)
    assert first.digest() != second.digest()


def test_every_seller_sells_something(book):
    sellers_with_orders = {order.seller_id for order in book.orders}
    assert len(sellers_with_orders) == len(book.sellers)


def test_no_order_after_a_seller_leaves(book):
    exit_days = {seller.id: seller.exit_day for seller in book.sellers}
    assert all(order.day < exit_days[order.seller_id] for order in book.orders)


def test_no_order_outside_the_window(book):
    assert all(0 <= order.day < book.days for order in book.orders)


def test_refund_lags_stay_inside_the_stated_bound(book):
    lags = [refund.arrival_day - refund.sale_day for refund in book.refunds]
    assert min(lags) >= 2
    assert max(lags) <= MAX_REFUND_LAG


def test_every_refund_belongs_to_a_real_order(book):
    order_ids = {order.id for order in book.orders}
    assert all(refund.order_id in order_ids for refund in book.refunds)


def test_refund_never_exceeds_its_order_with_the_fee_booked_separately(book):
    amount = {order.id: order.amount_cents for order in book.orders}
    assert all(0 < refund.amount_cents <= amount[refund.order_id] for refund in book.refunds)


def test_gmv_and_refund_rate_are_plausible(book):
    gmv = book.gmv_cents
    assert 4_000_000_00 < gmv < 12_000_000_00
    assert 0.015 < book.refund_cost_cents / gmv < 0.06


def test_band_mix_matches_the_declared_shares(book):
    counts = Counter(seller.band for seller in book.sellers)
    assert counts["established"] > counts["new"] > counts["risky"]
    for band, params in BAND_PARAMS.items():
        share = counts[band] / len(book.sellers)
        assert abs(share - params["share"]) < 0.03


def test_the_shuffle_breaks_the_id_order(book):
    """Ids must not encode the band, or a tie break would know the answer."""
    bands = [seller.band for seller in book.sellers]
    assert bands != sorted(bands)
    assert len({seller.band for seller in book.sellers[:20]}) > 1


def test_horizon_covers_the_last_refund(book):
    assert book.horizon > max(refund.arrival_day for refund in book.refunds)


def test_the_book_is_labelled_synthetic_in_its_metadata(book):
    assert book.seed == 20261127
