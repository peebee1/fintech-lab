from mandate.evals import percentile
from mandate.money import bps, format_minor


def test_minor_units_format_without_float_math():
    assert format_minor(149900, "INR") == "INR 1,499.00"
    assert format_minor(999, "EUR") == "EUR 9.99"
    assert format_minor(0, "EUR") == "EUR 0.00"
    assert format_minor(-250, "EUR") == "-EUR 2.50"


def test_basis_points_round_half_up_on_integers():
    assert bps(1, 3) == 3333
    assert bps(9948, 10000) == 9948
    assert bps(5, 0) == 0


def test_percentile_is_nearest_rank_and_deterministic():
    values = [0, 0, 0, 14, 14, 1, 2]
    assert percentile(values, 50) == 1
    assert percentile(values, 90) == 14
    assert percentile([], 50) is None
    assert percentile(values, 50) == percentile(list(reversed(values)), 50)
