from qualification.book import code_order_is_precedence, failures, generate_book


def test_same_seed_gives_the_same_book():
    a = generate_book(seed=11, days=4, per_day=300)
    b = generate_book(seed=11, days=4, per_day=300)
    assert a.transactions == b.transactions


def test_a_different_seed_gives_a_different_book():
    a = generate_book(seed=11, days=4, per_day=300)
    b = generate_book(seed=12, days=4, per_day=300)
    assert a.transactions != b.transactions


def test_every_transaction_follows_the_rate_card_precedence():
    book = generate_book(seed=11, days=4, per_day=400)
    assert code_order_is_precedence(book)
    for tx in book.transactions:
        codes = failures(tx)
        assert len(codes) == len(set(codes))


def test_volume_survives_a_change_in_how_many_fields_are_missing():
    messy = generate_book(seed=11, days=4, per_day=300)
    tidy = generate_book(seed=11, days=4, per_day=300, gap_scale=0.4)
    assert messy.processed_cents() == tidy.processed_cents()
    assert [t.amount_cents for t in messy.transactions] == [t.amount_cents for t in tidy.transactions]
    messy_failing = sum(1 for t in messy.transactions if failures(t))
    tidy_failing = sum(1 for t in tidy.transactions if failures(t))
    assert tidy_failing < messy_failing


def test_counts_add_up_and_the_book_is_plausible():
    book = generate_book(seed=20261120)
    assert 40_000 <= len(book.transactions) <= 80_000
    assert sum(book.by_channel().values()) == len(book.transactions)
    assert sum(book.by_product().values()) == len(book.transactions)
    processed = book.processed_cents()
    assert 500_000_000 < processed < 2_000_000_000
    commercial = [t for t in book.transactions if t.commercial]
    assert commercial, "the book needs commercial cards for the Level 2 rule to matter"
    assert any(t.amount_cents >= 500_000 for t in commercial)


def test_days_and_weekday_shape_reach_every_field():
    book = generate_book(seed=20261120, days=7, per_day=500)
    assert book.days == 7
    assert {t.day for t in book.transactions} == set(range(7))
    assert any(t.channel == "recurring" for t in book.transactions)
    assert any(not t.avs_ok for t in book.transactions)
    assert any(not t.same_day_batch for t in book.transactions)
