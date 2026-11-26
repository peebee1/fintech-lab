"""The book: deterministic, labelled, and the deductions are ground truth."""

from corrfee.book import AMOUNT_CEILING, AMOUNT_FLOOR, CORRIDORS, expected_bps, generate


def test_the_same_seed_builds_the_same_book():
    a, b = generate(), generate()
    assert a.total_cents() == b.total_cents()
    assert a.deductions_cents() == b.deductions_cents()
    assert [inv.id for inv in a.invoices] == [inv.id for inv in b.invoices]


def test_a_different_seed_builds_a_different_book():
    a, b = generate(seed=1), generate(seed=2)
    assert a.total_cents() != b.total_cents()
    assert a.deductions_cents() != b.deductions_cents()


def test_every_invoice_is_inside_the_stated_bounds(book):
    assert len(book.invoices) == 2_000
    for inv in book.invoices:
        assert AMOUNT_FLOOR <= inv.amount_cents <= AMOUNT_CEILING
        assert inv.amount_cents % 100 == 0, "invoices are whole units"
        assert 0 <= inv.day < book.days


def test_the_hop_count_is_a_property_of_the_corridor(book):
    lookup = {corridor.code: corridor.hops for corridor in CORRIDORS}
    for inv in book.invoices:
        assert inv.hops_count == lookup[inv.corridor]
        assert len(inv.hops) == inv.hops_count
        assert [hop.index for hop in inv.hops] == list(range(1, inv.hops_count + 1))


def test_deductions_are_the_sum_of_the_chain(book):
    for inv in book.invoices:
        assert inv.deductions_cents == sum(h.fee_cents for h in inv.hops) + inv.receiver_fee_cents
        assert inv.deductions_cents < inv.amount_cents


def test_the_book_has_one_two_and_three_hop_corridors(book):
    assert {inv.hops_count for inv in book.invoices} == {1, 2, 3}


def test_the_book_size_is_plausible(book):
    # A median ticket near USD 4,200 and a book under USD 15M for a quarter. The
    # first draft of this book had mu set on dollars in a cents field and came out
    # at USD 40k, which every check still passed.
    amounts = sorted(inv.amount_cents for inv in book.invoices)
    median = amounts[len(amounts) // 2]
    assert 300_000 <= median <= 600_000
    assert 10_000_000_00 <= book.total_cents() <= 15_000_000_00


def test_the_chain_takes_a_plausible_share(book):
    share_bps = book.deductions_cents() * 10_000 / book.total_cents()
    assert 20 <= share_bps <= 60


def test_longer_chains_cost_more(book):
    bps = expected_bps(book)
    one_hop = [bps[c.code] for c in CORRIDORS if c.hops == 1]
    three_hop = [bps[c.code] for c in CORRIDORS if c.hops == 3]
    assert max(one_hop) < min(three_hop)


def test_every_hop_fee_is_inside_its_floor_and_cap(book):
    for inv in book.invoices:
        for hop in inv.hops:
            assert hop.fee_cents == 0 or 1_200 <= hop.fee_cents <= 20_000


def test_some_hops_charge_nothing(book):
    zeros = sum(1 for inv in book.invoices for hop in inv.hops if hop.fee_cents == 0)
    charged = sum(1 for inv in book.invoices for hop in inv.hops if hop.fee_cents > 0)
    assert zeros > 0 and charged > 0, "a chain where every hop charges is a different book"
