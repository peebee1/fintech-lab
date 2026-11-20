"""Bench: measure the qualification gap, the repair curve, and the rate cut."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .audit import Audit, FixRow, audit
from .book import Book, generate_book
from .card import PRODUCTS, RULES

RESULTS = Path(__file__).resolve().parents[1] / "results"


def usd(cents: int) -> str:
    return f"{cents / 100:,.2f}"


def bps(cents: int, base: int) -> float:
    return round(cents / base * 10_000, 2) if base else 0.0


def _fix_row(row: FixRow) -> dict:
    return {
        "codes": list(row.codes),
        "recovery_cents": row.recovery_cents,
        "share": row.share,
        "transactions": row.transactions,
        "effort": row.effort,
    }


def _cause_rows(result: Audit) -> list[dict]:
    single = {row.codes[0]: row for row in result.single}
    out = []
    for cause in result.by_cause:
        fixed = single[cause.code]
        out.append(
            {
                "code": cause.code,
                "label": cause.label,
                "fix": cause.fix,
                "effort": cause.effort,
                "transactions": cause.transactions,
                "gap_cents": cause.gap_cents,
                "share": cause.share,
                "recovery_alone_cents": fixed.recovery_cents,
                "masked_cents": cause.gap_cents - fixed.recovery_cents,
                "recovery_alone_share": round(fixed.recovery_cents / cause.gap_cents, 6) if cause.gap_cents else 0.0,
            }
        )
    return out


def _book_summary(book: Book) -> dict:
    commercial = sum(1 for t in book.transactions if t.commercial)
    large = sum(1 for t in book.transactions if t.commercial and t.amount_cents >= 500_000)
    return {
        "transactions": len(book.transactions),
        "days": book.days,
        "processed_cents": book.processed_cents(),
        "by_channel": book.by_channel(),
        "by_product": book.by_product(),
        "commercial_transactions": commercial,
        "large_commercial_transactions": large,
    }


@lru_cache(maxsize=4)
def build(seed: int = 20261120, gap_scale: float = 1.0) -> dict:
    book = generate_book(seed, gap_scale=gap_scale)
    result = audit(book)
    causes = _cause_rows(result)

    best_pair = result.pairs[0]
    best_triple = result.triples[0]
    best_single = max(result.single, key=lambda r: r.recovery_cents)
    biggest_cause = max(causes, key=lambda c: c["gap_cents"])
    rate_cut_5 = result.rate_cuts[5]

    payload = {
        "synthetic": True,
        "seed": seed,
        "gap_scale": gap_scale,
        "book": _book_summary(book),
        "totals": {
            "billed_cents": result.billed_cents,
            "qualified_cents": result.qualified_cents,
            "gap_cents": result.gap_cents,
            "gap_bp_of_processed": bps(result.gap_cents, result.processed_cents),
            "gap_share_of_billed": round(result.gap_cents / result.billed_cents, 6) if result.billed_cents else 0.0,
            "failing_transactions": result.failing,
            "clean_transactions": result.clean,
        },
        "by_cause": causes,
        "single_fixes": [_fix_row(r) for r in result.single],
        "best_pairs": [_fix_row(r) for r in result.pairs[:4]],
        "best_triples": [_fix_row(r) for r in result.triples[:3]],
        "budget_curve": [_fix_row(r) for r in result.budget_curve],
        "rate_cuts": [
            {"bp": bp, "saving_cents": cents, "share_of_gap": round(cents / result.gap_cents, 6)}
            for bp, cents in sorted(result.rate_cuts.items())
        ],
        "headline": {
            "gap_cents": result.gap_cents,
            "gap_bp_of_processed": bps(result.gap_cents, result.processed_cents),
            "gap_share_of_billed": round(result.gap_cents / result.billed_cents, 6),
            "top_cause": biggest_cause["code"],
            "top_cause_cents": biggest_cause["gap_cents"],
            "top_cause_share": biggest_cause["share"],
            "top_cause_transactions": biggest_cause["transactions"],
            "best_single_codes": list(best_single.codes),
            "best_single_cents": best_single.recovery_cents,
            "best_single_share": best_single.share,
            "best_pair_codes": list(best_pair.codes),
            "best_pair_cents": best_pair.recovery_cents,
            "best_pair_share": best_pair.share,
            "best_triple_codes": list(best_triple.codes),
            "best_triple_cents": best_triple.recovery_cents,
            "best_triple_share": best_triple.share,
            "sum_of_single_cents": sum(r.recovery_cents for r in result.single),
            "cascade_cents": result.gap_cents - sum(r.recovery_cents for r in result.single),
            "all_fixes_cents": result.gap_cents,
            "rate_cut_5bp_cents": rate_cut_5,
            "rate_cut_5bp_share_of_gap": round(rate_cut_5 / result.gap_cents, 6),
            "pair_over_rate_cut": round(best_pair.recovery_cents / rate_cut_5, 3) if rate_cut_5 else 0.0,
        },
    }

    if gap_scale == 1.0:
        clean_book = generate_book(seed, gap_scale=0.4)
        clean = audit(clean_book)
        clean_pair = clean.pairs[0]
        payload["stress"] = {
            "gap_scale": 0.4,
            "label": "well integrated merchant",
            "processed_cents": clean.processed_cents,
            "billed_cents": clean.billed_cents,
            "gap_cents": clean.gap_cents,
            "gap_share_of_billed": round(clean.gap_cents / clean.billed_cents, 6),
            "best_pair_codes": list(clean_pair.codes),
            "best_pair_cents": clean_pair.recovery_cents,
            "best_pair_share": clean_pair.share,
            "rate_cut_5bp_cents": clean.rate_cuts[5],
        }
    return payload


def render_markdown(payload: dict) -> str:
    book = payload["book"]
    totals = payload["totals"]
    head = payload["headline"]
    lines = [
        "# fee qualification results",
        "",
        "Generated by `python -m qualification.cli bench`. Synthetic book, seed "
        f"{payload['seed']}, {book['transactions']:,} transactions over {book['days']} days, "
        f"USD {usd(book['processed_cents'])} processed.",
        "",
        "## What the merchant paid, and what full qualification would have cost",
        "",
        f"- Billed: USD {usd(totals['billed_cents'])}",
        f"- Fully qualified: USD {usd(totals['qualified_cents'])}",
        f"- Gap: USD {usd(totals['gap_cents'])} ({totals['gap_bp_of_processed']} bps of processed value, "
        f"{totals['gap_share_of_billed'] * 100:.2f}% of the bill)",
        f"- Transactions with at least one gap: {totals['failing_transactions']:,} of "
        f"{book['transactions']:,}",
        "",
        "## Gap by the rule that binds",
        "",
        "The gap partitions exactly: one row per transaction, at the highest uplift it fails.",
        "The last two columns are the part of that named cause a single fix actually collects,",
        "and the part that stays behind because another failure outranks it.",
        "",
        "| Rule | Transactions | Gap USD | Share | Recovered by that fix alone | Left behind |",
        "|---|---|---|---|---|---|",
    ]
    for cause in payload["by_cause"]:
        lines.append(
            f"| {cause['code']} | {cause['transactions']:,} | {usd(cause['gap_cents'])} | "
            f"{cause['share'] * 100:.1f}% | {usd(cause['recovery_alone_cents'])} | "
            f"{usd(cause['masked_cents'])} |"
        )

    lines += [
        "",
        "## Repair budget: the best set of fixes at each size",
        "",
        "| Fixes | Rules | Recovered USD | Share of gap | Marginal USD | Transactions moved |",
        "|---|---|---|---|---|---|",
    ]
    previous = 0
    for row in payload["budget_curve"]:
        label = ", ".join(row["codes"]) if row["codes"] else "none"
        marginal = row["recovery_cents"] - previous
        previous = row["recovery_cents"]
        lines.append(
            f"| {len(row['codes'])} | {label} | {usd(row['recovery_cents'])} | "
            f"{row['share'] * 100:.1f}% | {usd(marginal)} | {row['transactions']:,} |"
        )

    lines += [
        "",
        "## Best pairs and triples",
        "",
        "| Rules | Recovered USD | Share of gap | Transactions moved | Effort units |",
        "|---|---|---|---|---|",
    ]
    for row in payload["best_pairs"][:3]:
        lines.append(
            f"| {', '.join(row['codes'])} | {usd(row['recovery_cents'])} | {row['share'] * 100:.1f}% | "
            f"{row['transactions']:,} | {row['effort']} |"
        )
    for row in payload["best_triples"][:2]:
        lines.append(
            f"| {', '.join(row['codes'])} | {usd(row['recovery_cents'])} | {row['share'] * 100:.1f}% | "
            f"{row['transactions']:,} | {row['effort']} |"
        )

    lines += [
        "",
        "## The same book at a negotiated rate",
        "",
        "| Cut | Saving USD | Share of the data gap |",
        "|---|---|---|",
    ]
    for row in payload["rate_cuts"]:
        lines.append(f"| {row['bp']} bps | {usd(row['saving_cents'])} | {row['share_of_gap'] * 100:.1f}% |")

    lines += [
        "",
        "## Headline",
        "",
        f"- The largest single cause is `{head['top_cause']}`: USD {usd(head['top_cause_cents'])}, "
        f"{head['top_cause_share'] * 100:.1f}% of the gap across {head['top_cause_transactions']:,} transactions.",
        f"- One fix, `{head['best_single_codes'][0]}`, recovers USD {usd(head['best_single_cents'])} "
        f"({head['best_single_share'] * 100:.1f}% of the gap).",
        f"- The best pair, {' and '.join(head['best_pair_codes'])}, recovers USD "
        f"{usd(head['best_pair_cents'])} ({head['best_pair_share'] * 100:.1f}%).",
        f"- Fixing each rule on its own and adding the rows claims USD {usd(head['sum_of_single_cents'])}, "
        f"USD {usd(head['cascade_cents'])} less than the gap: that difference is the part of a named cause "
        "that stays behind until the rule above it is fixed.",
        f"- A 5 bps rate cut on the same book saves USD {usd(head['rate_cut_5bp_cents'])}, "
        f"{head['rate_cut_5bp_share_of_gap'] * 100:.1f}% of the data gap.",
        "",
        "Rules and their modelled uplift: "
        + ", ".join(f"{r.code} {r.uplift_bp} bps" for r in RULES)
        + ".",
        "",
    ]

    if "stress" in payload:
        stress = payload["stress"]
        lines += [
            "## Stress: the same analysis on a well integrated book",
            "",
            f"The same seed and the same volume with every missing field probability at "
            f"{stress['gap_scale']}x. Billed USD {usd(stress['billed_cents'])}, gap USD "
            f"{usd(stress['gap_cents'])} ({stress['gap_share_of_billed'] * 100:.2f}% of the bill). "
            f"The best pair is {' and '.join(stress['best_pair_codes'])}, USD "
            f"{usd(stress['best_pair_cents'])} ({stress['best_pair_share'] * 100:.1f}% of that gap), against "
            f"USD {usd(stress['rate_cut_5bp_cents'])} for a 5 bps cut.",
            "",
        ]
    return "\n".join(lines)


def write_results(directory: Path | None = None, seed: int = 20261120) -> Path:
    directory = RESULTS if directory is None else directory
    payload = build(seed)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return directory


def summarise(payload: dict) -> list[str]:
    head = payload["headline"]
    book = payload["book"]
    return [
        f"book: {book['transactions']:,} transactions, USD {usd(book['processed_cents'])} processed",
        f"billed USD {usd(payload['totals']['billed_cents'])}, "
        f"qualified USD {usd(payload['totals']['qualified_cents'])}, "
        f"gap USD {usd(head['gap_cents'])} ({head['gap_bp_of_processed']} bps)",
        f"gap share of bill: {head['gap_share_of_billed'] * 100:.2f}%",
        f"top cause: {head['top_cause']} USD {usd(head['top_cause_cents'])}",
        f"best single: {head['best_single_codes'][0]} USD {usd(head['best_single_cents'])}",
        f"best pair: {'+'.join(head['best_pair_codes'])} USD {usd(head['best_pair_cents'])} "
        f"({head['best_pair_share'] * 100:.1f}% of gap)",
        f"5 bps rate cut: USD {usd(head['rate_cut_5bp_cents'])}, "
        f"pair is {head['pair_over_rate_cut']}x the cut",
        f"products: {', '.join(f'{k} {v:,}' for k, v in book['by_product'].items())}",
        f"rules priced: {', '.join(f'{r.code}={r.uplift_bp}bp' for r in RULES)}",
        f"product base rates: "
        + ", ".join(f"{p.code}={p.qualified_bp}bp" for p in PRODUCTS.values()),
    ]
