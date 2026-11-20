"""Price the gap between what was billed and what full qualification would cost.

Three things are computed, all from the same book:

1. the gap and its partition by the rule that actually binds
2. the recovery from fixing one, two or three rules, including the precedence
   effect that makes a sum of single fix impacts overstate what you can collect
3. the same book priced against a negotiated rate cut, in basis points
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .book import Book, Transaction, failures
from .card import (
    QUALIFIED_INDEX,
    RULE_CODES,
    RULE_INDEX,
    RULES,
    RULES_BY_CODE,
    cut_cents,
    fee_cents,
)


@dataclass(frozen=True)
class TxRow:
    fails: tuple[int, ...]
    fees: tuple[int, ...]
    billed: int
    qualified: int


@dataclass(frozen=True)
class CauseRow:
    code: str
    label: str
    fix: str
    effort: int
    transactions: int
    gap_cents: int
    share: float


@dataclass(frozen=True)
class FixRow:
    codes: tuple[str, ...]
    recovery_cents: int
    share: float
    transactions: int
    effort: int


@dataclass(frozen=True)
class Audit:
    processed_cents: int
    billed_cents: int
    qualified_cents: int
    gap_cents: int
    failing: int
    clean: int
    by_cause: tuple[CauseRow, ...]
    single: tuple[FixRow, ...]
    pairs: tuple[FixRow, ...]
    triples: tuple[FixRow, ...]
    budget_curve: tuple[FixRow, ...]
    rate_cuts: dict[int, int]


def _row(tx: Transaction) -> TxRow | None:
    codes = failures(tx)
    if not codes:
        return None
    fees = tuple(fee_cents(tx.amount_cents, tx.product, code) for code in RULE_CODES)
    qualified = fee_cents(tx.amount_cents, tx.product, None)
    return TxRow(
        fails=tuple(RULE_INDEX[c] for c in codes),
        fees=fees + (qualified,),
        billed=fees[RULE_INDEX[codes[0]]],
        qualified=qualified,
    )


def _fee_after(row: TxRow, fixed: frozenset[int]) -> int:
    for idx in row.fails:
        if idx not in fixed:
            return row.fees[idx]
    return row.fees[QUALIFIED_INDEX]


def _recovery(rows: tuple[TxRow, ...], binding: dict[int, tuple[TxRow, ...]], fixed: frozenset[int]) -> tuple[int, int]:
    """Recovery from a fix set, and the number of transactions it moves.

    Only transactions whose binding rule is in the set can change, so the scan is
    limited to those. That is an exact short cut, not an approximation.
    """
    total = 0
    moved = 0
    for idx in sorted(fixed):
        for row in binding.get(idx, ()):
            after = _fee_after(row, fixed)
            delta = row.billed - after
            if delta:
                total += delta
                moved += 1
    return total, moved


def _labelled(codes: tuple[str, ...], recovery: int, moved: int, gap: int) -> FixRow:
    effort = sum(RULES_BY_CODE[c].effort for c in codes)
    return FixRow(
        codes=codes,
        recovery_cents=recovery,
        share=round(recovery / gap, 6) if gap else 0.0,
        transactions=moved,
        effort=effort,
    )


def audit(book: Book) -> Audit:
    rows: list[TxRow] = []
    billed_total = 0
    qualified_total = 0
    for tx in book.transactions:
        row = _row(tx)
        if row is None:
            qualified_total += fee_cents(tx.amount_cents, tx.product, None)
            billed_total += fee_cents(tx.amount_cents, tx.product, None)
            continue
        rows.append(row)
        billed_total += row.billed
        qualified_total += row.qualified

    fixed_rows = tuple(rows)
    gap = billed_total - qualified_total

    binding_lists: dict[int, list[TxRow]] = {i: [] for i in range(len(RULES))}
    cause_gap = {code: 0 for code in RULE_CODES}
    cause_count = {code: 0 for code in RULE_CODES}
    for row in rows:
        first = row.fails[0]
        binding_lists[first].append(row)
        code = RULE_CODES[first]
        cause_gap[code] += row.billed - row.qualified
        cause_count[code] += 1
    binding = {k: tuple(v) for k, v in binding_lists.items()}

    by_cause = tuple(
        CauseRow(
            code=rule.code,
            label=rule.label,
            fix=rule.fix,
            effort=rule.effort,
            transactions=cause_count[rule.code],
            gap_cents=cause_gap[rule.code],
            share=round(cause_gap[rule.code] / gap, 6) if gap else 0.0,
        )
        for rule in RULES
    )

    single = tuple(
        _labelled((code,), *_recovery(fixed_rows, binding, frozenset({RULE_INDEX[code]})), gap)
        for code in RULE_CODES
    )

    pair_rows = []
    for combo in combinations(RULE_CODES, 2):
        fixed = frozenset(RULE_INDEX[c] for c in combo)
        pair_rows.append(_labelled(combo, *_recovery(fixed_rows, binding, fixed), gap))
    pairs = tuple(sorted(pair_rows, key=lambda r: (-r.recovery_cents, r.codes)))

    triple_rows = []
    for combo in combinations(RULE_CODES, 3):
        fixed = frozenset(RULE_INDEX[c] for c in combo)
        triple_rows.append(_labelled(combo, *_recovery(fixed_rows, binding, fixed), gap))
    triples = tuple(sorted(triple_rows, key=lambda r: (-r.recovery_cents, r.codes)))

    curve = [_labelled((), 0, 0, gap)]
    for size in (1, 2, 3):
        pool = {1: single, 2: pairs, 3: triples}[size]
        curve.append(max(pool, key=lambda r: r.recovery_cents))
    all_fixed = frozenset(range(len(RULES)))
    curve.append(_labelled(RULE_CODES, *_recovery(fixed_rows, binding, all_fixed), gap))
    budget_curve = tuple(curve)

    rate_cuts = {bp: sum(cut_cents(tx.amount_cents, bp) for tx in book.transactions) for bp in (5, 10, 25)}

    return Audit(
        processed_cents=book.processed_cents(),
        billed_cents=billed_total,
        qualified_cents=qualified_total,
        gap_cents=gap,
        failing=len(rows),
        clean=len(book.transactions) - len(rows),
        by_cause=by_cause,
        single=single,
        pairs=pairs,
        triples=triples,
        budget_curve=budget_curve,
        rate_cuts=rate_cuts,
    )
