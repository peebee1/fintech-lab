from authholds.book import HORIZON, LAST_CAPTURE_DAY, MAX_EXPIRY_DAYS, generate_book


def test_generation_is_deterministic():
    assert generate_book(7).auths == generate_book(7).auths
    assert generate_book(7).auths != generate_book(8).auths


def test_ids_carry_no_information_about_the_capture_schedule():
    book = generate_book(20261119)
    ids = [a.auth_id for a in book.auths]
    assert ids == list(range(1, len(book.auths) + 1))
    first_half = sum(1 for a in book.auths[: len(book.auths) // 2] if not a.captures)
    second_half = sum(1 for a in book.auths[len(book.auths) // 2 :] if not a.captures)
    # never captured authorisations are shuffled through the numbering
    assert abs(first_half - second_half) <= max(5, len(book.auths) // 100)


def test_book_size_is_plausible():
    book = generate_book(20261119)
    mean_ticket = book.requested_cents / len(book.auths)
    assert 100_00 <= mean_ticket <= 400_00, mean_ticket
    assert 200_000_00 <= book.requested_cents <= 1_500_000_00
    assert set(book.by_kind()) == {"restaurant", "retail", "split", "hotel", "late"}


def test_every_capture_lands_after_approval_and_inside_the_horizon():
    book = generate_book(20261119)
    for auth in book.auths:
        assert auth.approved_day >= 0
        for capture in auth.captures:
            assert capture.day >= auth.approved_day
            assert capture.day - auth.approved_day <= LAST_CAPTURE_DAY
            assert capture.day < book.horizon
            assert capture.cents > 0
    assert book.horizon == HORIZON
    assert HORIZON > 170 + LAST_CAPTURE_DAY + MAX_EXPIRY_DAYS


def test_split_captures_sum_to_the_authorised_amount():
    book = generate_book(20261119)
    splits = [a for a in book.auths if a.kind == "split" and a.captures]
    assert splits
    for auth in splits:
        assert auth.requested_cents == auth.authorized_cents


def test_hotel_authorisation_exceeds_the_bill_and_tips_exceed_the_authorisation():
    book = generate_book(20261119)
    hotels = [a for a in book.auths if a.kind == "hotel" and a.captures]
    restaurants = [a for a in book.auths if a.kind == "restaurant" and a.captures]
    assert all(a.requested_cents < a.authorized_cents for a in hotels)
    assert all(a.requested_cents > a.authorized_cents for a in restaurants)
