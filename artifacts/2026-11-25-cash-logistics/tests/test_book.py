"""The book: deterministic, shaped, and free of any wall clock."""

from cashplan.book import KINDS, NOTES_PER_CASSETTE, SURGE_DAYS, generate


def test_generation_is_deterministic():
    one = generate(seed=7, days=30)
    two = generate(seed=7, days=30)
    assert [r.notes for r in one.rows[0]] == [r.notes for r in two.rows[0]]
    assert one.notes_dispensed() == two.notes_dispensed()


def test_seed_changes_the_book():
    one = generate(seed=7, days=30)
    two = generate(seed=8, days=30)
    assert one.notes_dispensed() != two.notes_dispensed()


def test_site_counts_and_capacity():
    book = generate(days=10)
    assert len(book.sites) == sum(kind[1] for kind in KINDS)
    for site in book.sites:
        assert site.capacity == site.cassettes * NOTES_PER_CASSETTE
        assert 0 < site.opening < site.capacity


def test_every_site_demands_cash_and_demand_is_never_negative(book):
    for site in book.sites:
        assert book.site_notes(site.id) > 0
        assert all(row.notes >= 0 and row.withdrawals >= 0 for row in book.rows[site.id])


def test_the_surge_is_visible_in_the_book(book):
    surge = [row.notes for site in book.sites for row in book.rows[site.id] if row.day in SURGE_DAYS]
    normal = [row.notes for site in book.sites for row in book.rows[site.id] if row.day not in SURGE_DAYS]
    assert sum(surge) / len(surge) > 1.3 * (sum(normal) / len(normal))


def test_metro_sites_carry_more_than_low_traffic_sites(book):
    metro = [site for site in book.sites if site.kind == "metro"]
    low = [site for site in book.sites if site.kind == "low_traffic"]
    per_metro = sum(book.site_notes(s.id) for s in metro) / len(metro)
    per_low = sum(book.site_notes(s.id) for s in low) / len(low)
    assert per_metro > 5 * per_low
