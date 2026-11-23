from exempt.book import MAX_CENTS, MIN_CENTS, generate


def test_generation_is_deterministic():
    assert generate(7, days=5, per_day=50) == generate(7, days=5, per_day=50)


def test_different_seeds_differ():
    assert generate(7, days=5, per_day=50) != generate(8, days=5, per_day=50)


def test_amounts_and_order():
    book = generate(11, days=4, per_day=30)
    assert all(MIN_CENTS <= t.amount_cents <= MAX_CENTS for t in book.txns)
    assert [t.id for t in book.txns] == list(range(len(book.txns)))
    assert all(0 <= t.day < book.days for t in book.txns)
    assert [t.day for t in book.txns] == sorted(t.day for t in book.txns)


def test_mean_ticket_is_plausible_for_the_domain():
    # A log normal median near EUR 38 must produce a mean ticket in the same order,
    # not one off by a factor of ten in either direction.
    book = generate(20261123, days=10, per_day=200)
    assert 4000 <= book.mean_ticket_cents() <= 9000


def test_latent_fraud_share_is_plausible():
    book = generate(20261123, days=20, per_day=200)
    assert 5.0 <= book.latent_fraud_bps() <= 40.0


def test_draws_are_probabilities():
    book = generate(3, days=3, per_day=40)
    assert all(0.0 <= t.abandon_draw < 1.0 and 0.0 <= t.stop_draw < 1.0 for t in book.txns)
