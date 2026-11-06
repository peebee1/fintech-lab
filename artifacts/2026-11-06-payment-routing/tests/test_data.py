"""The book is synthetic, deterministic, and in range."""

from routelab import data


def test_same_seed_same_book():
    assert data.digest(data.build(500, seed=3)) == data.digest(data.build(500, seed=3))


def test_different_seed_different_book():
    assert data.digest(data.build(500, seed=3)) != data.digest(data.build(500, seed=4))


def test_amounts_stay_inside_their_band():
    for txn in data.build(2000, seed=11):
        low, high = data.BAND_RANGE[txn.band]
        assert low <= txn.amount <= high


def test_every_context_appears(book):
    contexts = {txn.context for txn in book}
    assert len(contexts) == 12
    assert sum(data.mix(book).values()) == 1.0


def test_band_mix_is_roughly_honoured():
    counts = {"micro": 0, "mid": 0, "large": 0}
    for txn in data.build(20000, seed=5):
        counts[txn.band] += 1
    assert 0.22 < counts["micro"] / 20000 < 0.28
    assert 0.27 < counts["large"] / 20000 < 0.33


def test_fee_rounds_half_up_in_cents():
    # 1.20 percent of 1001 cents is 12.012 cents, so 12, plus the fixed 8
    assert data.fee_cents(1001, 120, 8) == 20
    # 1.85 percent of 1000 is exactly 18.5 cents, which rounds up
    assert data.fee_cents(1000, 185, 0) == 19


def test_margin_rounds_half_up():
    assert data.margin_cents(1000, 1500) == 150
    assert data.margin_cents(333, 1500) == 50
