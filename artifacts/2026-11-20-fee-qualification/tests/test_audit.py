from itertools import combinations

from qualification.audit import audit
from qualification.book import binding_tier, generate_book
from qualification.card import RULE_CODES, fee_cents


def brute_recovery(book, fixed_codes) -> int:
    """Recovery computed transaction by transaction, with no short cuts."""
    fixed = frozenset(fixed_codes)
    total = 0
    for tx in book.transactions:
        before = fee_cents(tx.amount_cents, tx.product, binding_tier(tx))
        after = fee_cents(tx.amount_cents, tx.product, binding_tier(tx, fixed))
        total += before - after
    return total


def test_the_gap_partitions_exactly_by_the_rule_that_binds():
    result = audit(generate_book(seed=5, days=3, per_day=250))
    assert sum(c.gap_cents for c in result.by_cause) == result.gap_cents
    assert sum(c.transactions for c in result.by_cause) == result.failing
    assert result.billed_cents - result.qualified_cents == result.gap_cents


def test_fixing_every_rule_removes_the_whole_gap():
    result = audit(generate_book(seed=5, days=3, per_day=250))
    assert result.budget_curve[-1].recovery_cents == result.gap_cents
    assert result.budget_curve[-1].share == 1.0


def test_the_bottom_rule_can_never_be_masked_and_the_rest_can():
    result = audit(generate_book(seed=20261120))
    causes = {c.code: c for c in result.by_cause}
    singles = {r.codes[0]: r for r in result.single}
    bottom = RULE_CODES[-1]
    assert causes[bottom].gap_cents == singles[bottom].recovery_cents
    assert any(causes[c].gap_cents > singles[c].recovery_cents for c in RULE_CODES[:-1])


def test_single_fixes_are_never_larger_than_the_cause_they_price():
    result = audit(generate_book(seed=5, days=3, per_day=250))
    causes = {c.code: c for c in result.by_cause}
    for row in result.single:
        assert 0 <= row.recovery_cents <= causes[row.codes[0]].gap_cents


def test_more_fixes_never_recover_less():
    book = generate_book(seed=5, days=3, per_day=250)
    result = audit(book)
    singles = {r.codes[0]: r.recovery_cents for r in result.single}
    for row in result.pairs:
        a, b = row.codes
        assert row.recovery_cents >= max(singles[a], singles[b])
    for row in result.budget_curve:
        if len(row.codes) > 1:
            assert row.recovery_cents >= max(
                r.recovery_cents for r in result.single if r.codes[0] in row.codes
            )


def test_the_fast_path_matches_a_transaction_by_transaction_recount():
    book = generate_book(seed=7, days=3, per_day=220, gap_scale=3.0)
    result = audit(book)
    for row in result.single:
        assert row.recovery_cents == brute_recovery(book, row.codes)
    for combo in combinations(RULE_CODES, 2):
        row = next(r for r in result.pairs if r.codes == combo)
        assert row.recovery_cents == brute_recovery(book, combo)
    for combo in combinations(RULE_CODES, 3):
        row = next(r for r in result.triples if r.codes == combo)
        assert row.recovery_cents == brute_recovery(book, combo)


def test_the_best_pair_is_the_best_of_every_pair():
    book = generate_book(seed=7, days=3, per_day=220, gap_scale=3.0)
    result = audit(book)
    every = {combo: brute_recovery(book, combo) for combo in combinations(RULE_CODES, 2)}
    assert result.pairs[0].recovery_cents == max(every.values())


def test_rate_cuts_save_money_in_proportion_to_the_cut():
    book = generate_book(seed=5, days=3, per_day=250)
    result = audit(book)
    assert 0 < result.rate_cuts[5] < result.rate_cuts[10] < result.rate_cuts[25]
    # Rounding is per item, so the 10 bps saving can differ from twice the 5 bps
    # saving by at most one cent per transaction.
    assert abs(result.rate_cuts[10] - 2 * result.rate_cuts[5]) <= len(book.transactions)
