from exempt.rules import (
    LOW_VALUE_CAP_CENTS,
    bps,
    down_one,
    highest_etv,
    low_value_allows,
    reference_bps,
)


def test_ladder_boundaries_are_inclusive_where_the_rule_is():
    assert highest_etv(None) == 0
    assert highest_etv(0.0) == 50000
    assert highest_etv(1.0) == 50000
    assert highest_etv(1.01) == 25000
    assert highest_etv(6.0) == 25000
    assert highest_etv(6.01) == 10000
    assert highest_etv(13.0) == 10000
    assert highest_etv(13.01) == 0


def test_reference_rates_are_the_cited_table():
    assert reference_bps(50000) == 1.0
    assert reference_bps(25000) == 6.0
    assert reference_bps(10000) == 13.0
    assert reference_bps(0) is None


def test_low_value_amount_cap():
    assert low_value_allows(LOW_VALUE_CAP_CENTS, 0, 0)
    assert not low_value_allows(LOW_VALUE_CAP_CENTS + 1, 0, 0)


def test_low_value_counter_limits():
    assert low_value_allows(2000, 4, 8000)
    assert not low_value_allows(2000, 5, 8000)
    assert low_value_allows(2000, 0, 8000)
    assert not low_value_allows(2001, 0, 8000)


def test_down_one_walks_off_the_ladder():
    assert down_one(50000) == 25000
    assert down_one(25000) == 10000
    assert down_one(10000) == 0
    assert down_one(0) == 0
    assert down_one(1234) == 0


def test_bps_zero_guard():
    assert bps(5, 0) == 0.0
    assert bps(50, 100000) == 5.0
