"""The central claim: an allocation either preserves the total or it does not."""

from fractions import Fraction

import pytest

from fxalloc.alloc import (
    AllocationError,
    METHODS,
    exact_shares,
    floor_to_largest,
    largest_remainder,
    naive_half_even,
    naive_half_up,
    reconcile,
)

FAMILIES = ((1, 1, 1), (1, 2, 3), (7, 2, 1), (1, 1, 1, 1), (2, 3, 5, 7), (1, 0, 1), (0, 0, 1), (999, 1))


def test_three_way_split_of_a_hundred_balances():
    assert largest_remainder(10_000, (1, 1, 1)) == [3334, 3333, 3333]


def test_per_share_half_up_loses_the_penny():
    parts = naive_half_up(10_000, (1, 1, 1))
    assert parts == [3333, 3333, 3333]
    assert sum(parts) == 9_999


def test_half_even_also_loses_the_penny():
    assert sum(naive_half_even(10_000, (1, 1, 1))) == 9_999


@pytest.mark.parametrize("weights", FAMILIES)
@pytest.mark.parametrize("method", sorted(METHODS))
def test_balancing_methods_preserve_the_total_for_every_small_total(method, weights):
    rule = METHODS[method]
    if method.startswith("naive"):
        return  # asserted separately: these are the methods that do not balance
    for total in range(0, 121):
        parts = rule(total, weights)
        assert sum(parts) == total, (method, weights, total, parts)


@pytest.mark.parametrize("weights", FAMILIES)
def test_largest_remainder_never_moves_a_party_a_full_unit(weights):
    for total in range(0, 121):
        parts = largest_remainder(total, weights)
        for part, share in zip(parts, exact_shares(total, weights)):
            assert abs(Fraction(part) - share) < 1


def test_refunds_mirror_charges():
    charge = largest_remainder(10_000, (1, 1, 1))
    refund = largest_remainder(-10_000, (1, 1, 1))
    assert refund == [-part for part in charge]
    assert sum(refund) == -10_000


def test_zero_weight_party_gets_nothing():
    assert largest_remainder(7, (0, 0, 1)) == [0, 0, 7]
    assert largest_remainder(101, (1, 0, 3))[1] == 0


def test_floor_to_largest_overpays_the_biggest_party():
    """101 split 1:2:3. The exact shares are 16.83, 33.67 and 50.50."""
    parts = floor_to_largest(101, (1, 2, 3))
    assert parts == [16, 33, 52]
    assert sum(parts) == 101
    assert Fraction(parts[2]) - Fraction(101 * 3, 6) == Fraction(3, 2)


def test_largest_remainder_takes_the_same_case_the_fair_way():
    assert largest_remainder(101, (1, 2, 3)) == [17, 34, 50]


def test_residual_equals_the_explained_gap_on_dirty_data():
    """Mixed sign rounding errors: the invariant a bare residual == 0 check misses."""
    weights = (1, 2, 3, 7)
    mixed = None
    for total in range(0, 400):
        parts = naive_half_up(total, weights)
        exact = exact_shares(total, weights)
        contributions = [Fraction(part) - share for part, share in zip(parts, exact)]
        if any(c > 0 for c in contributions) and any(c < 0 for c in contributions):
            record = reconcile(total, weights, parts)
            if record.residual != 0:
                mixed = record
                break
    assert mixed is not None, "expected a case with mixed sign errors and a nonzero residual"
    assert mixed.residual == mixed.explained
    assert mixed.residual != 0
    assert not mixed.balanced


def test_reconcile_flags_overpayment():
    record = reconcile(100, (1, 1, 1), [34, 34, 34])
    assert record.residual == -2
    assert record.overpaid
    assert record.residual == record.explained


def test_inputs_are_validated():
    with pytest.raises(AllocationError):
        largest_remainder(100, ())
    with pytest.raises(AllocationError):
        largest_remainder(100, (0, 0))
    with pytest.raises(AllocationError):
        largest_remainder(100, (-1, 2))
    with pytest.raises(AllocationError):
        largest_remainder(100.5, (1, 1))  # type: ignore[arg-type]
    with pytest.raises(AllocationError):
        largest_remainder(100, (1.0, 2))  # type: ignore[arg-type]
    with pytest.raises(AllocationError):
        largest_remainder(100, "12")  # type: ignore[arg-type]


def test_unknown_method_is_refused():
    from fxalloc.alloc import allocate

    with pytest.raises(AllocationError):
        allocate(100, (1, 1), "exact_magic")


def test_ties_break_by_party_index():
    """One unit, two equal parties: stable output, or last week's payout differs."""
    assert largest_remainder(1, (1, 1)) == [1, 0]
    assert largest_remainder(1, (1, 1)) == largest_remainder(1, (1, 1))
