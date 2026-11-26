"""The bench: replay the ladder, price the sweeps, write the quoted numbers."""

from __future__ import annotations

import json
from pathlib import Path

from .book import Book, expected_bps, generate
from .fees import our_fee, sender_bank_fee, sha_fee
from .policies import Policy, ladder
from .settle import CLAIM_OPS_CENTS, TOLERANCE_BPS, TOLERANCE_MIN_CENTS, Result, settle

RESULTS = Path(__file__).resolve().parents[1] / "results"
HEADLINE = "sha_none"
COMPARATOR = "our_all"
CLAIM_THRESHOLDS = (2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000)
TOLERANCES = (0, 1_000, 2_500, 5_000, 10_000, 25_000)


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def bps(value: int, total: int) -> float:
    return 0.0 if total == 0 else round(value * 10_000 / total, 3)


def _milli(value: float) -> int:
    return int(round(value * 1_000))


def _winners(book: Book) -> dict[str, str]:
    """Per corridor, the code with the lowest total cost over that corridor.

    SHA and BEN carry the same money, so SHA wins the tie by list order. The
    only real question a corridor answers is SHA or OUR.
    """
    out: dict[str, str] = {}
    for corridor in book.corridors:
        rows = book.with_corridor(corridor.code)
        totals = {
            "OUR": sum(our_fee(inv.amount_cents) for inv in rows),
            "SHA": sum(sha_fee(inv.amount_cents) + inv.deductions_cents for inv in rows),
            "BEN": sum(sender_bank_fee(inv.amount_cents) + inv.deductions_cents for inv in rows),
        }
        out[corridor.code] = min(("OUR", "SHA", "BEN"), key=lambda code: totals[code])
    return out


def _corridor_chooser(invoice, context):
    return context["winners"][invoice.corridor]


def _cost_chooser(invoice, context):
    amount = invoice.amount_cents
    expected = amount * context["milli"][invoice.corridor] // 10_000_000
    return "OUR" if our_fee(amount) < sha_fee(amount) + expected else "SHA"


def _oracle_chooser(invoice, context):
    amount = invoice.amount_cents
    chain = invoice.deductions_cents
    options = (
        ("OUR", our_fee(amount)),
        ("SHA", sha_fee(amount) + chain),
        ("BEN", sender_bank_fee(amount) + chain),
    )
    return min(options, key=lambda pair: pair[1])[0]


def policies() -> list[Policy]:
    out = []
    for policy in ladder():
        if policy.name == "corridor_rule":
            out.append(
                Policy(policy.name, policy.code, policy.repair, chooser=_corridor_chooser,
                       note=policy.note)
            )
        elif policy.name == "cost_rule":
            out.append(
                Policy(policy.name, policy.code, policy.repair, chooser=_cost_chooser,
                       note=policy.note)
            )
        elif policy.name == "oracle":
            out.append(
                Policy(policy.name, policy.code, policy.repair, chooser=_oracle_chooser,
                       note=policy.note)
            )
        else:
            out.append(policy)
    return out


def _row(result: Result) -> dict:
    return {
        "policy": result.policy,
        "code": result.code,
        "note": result.note,
        "invoices": result.invoices,
        "claims": result.claims,
        "repairs": result.repairs,
        "declined": result.declined,
        "tolerated": result.tolerated,
        "sender_fee_cents": result.sender_fee_cents,
        "repair_cents": result.repair_cents,
        "repair_fee_cents": result.repair_fee_cents,
        "ops_cents": result.ops_cents,
        "sender_total_cents": result.sender_total_cents,
        "supplier_cents": result.supplier_cents,
        "economic_total_cents": result.economic_cents,
        "sender_bps": result.sender_bps,
        "economic_bps": result.economic_bps,
        "delivered_ratio": round(result.delivered_cents / result.value_cents, 6),
    }


def _corridor_rows(book: Book, milli: dict[str, int]) -> list[dict]:
    rows = []
    for corridor in book.corridors:
        invoices = book.with_corridor(corridor.code)
        value = sum(inv.amount_cents for inv in invoices)
        taken = sum(inv.deductions_cents for inv in invoices)
        sha = sum(sha_fee(inv.amount_cents) for inv in invoices) + taken
        our = sum(our_fee(inv.amount_cents) for inv in invoices)
        rows.append(
            {
                "corridor": corridor.code,
                "route": f"{corridor.source}-{corridor.target}",
                "currency": corridor.currency,
                "hops": corridor.hops,
                "invoices": len(invoices),
                "value_cents": value,
                "deduction_cents": taken,
                "deduction_bps": bps(taken, value),
                "sha_bps": bps(sha, value),
                "our_bps": bps(our, value),
                "cheaper": "OUR" if our < sha else "SHA",
                "our_minus_sha_bps": round(bps(our, value) - bps(sha, value), 3),
                "share_pct": round(value * 100 / book.total_cents(), 2),
                "expected_milli": milli[corridor.code],
            }
        )
    return rows


def _breakeven(book: Book, milli: dict[str, int]) -> list[dict]:
    """Smallest invoice where OUR undercuts the corridor's expected SHA cost."""
    out = []
    for corridor in book.corridors:
        found = None
        amount = 35_000
        while amount <= 4_000_000:
            expected = amount * milli[corridor.code] // 10_000_000
            if our_fee(amount) < sha_fee(amount) + expected:
                found = amount
                break
            amount += 2_500
        out.append(
            {
                "corridor": corridor.code,
                "hops": corridor.hops,
                "breakeven_cents": found,
                "values_below_breakeven": None
                if found is None
                else sum(1 for inv in book.with_corridor(corridor.code) if inv.amount_cents < found),
            }
        )
    return out


def _claim_sweep(book: Book, context: dict) -> list[dict]:
    rows = []
    for threshold in CLAIM_THRESHOLDS:
        policy = Policy(f"sha_claim_{threshold}", "SHA", "above", threshold)
        result = settle(book, policy, context)
        rows.append(
            {
                "threshold_cents": threshold,
                "claims": result.claims,
                "repairs": result.repairs,
                "sender_bps": result.sender_bps,
                "supplier_bps": bps(result.supplier_cents, result.value_cents),
                "economic_bps": result.economic_bps,
            }
        )
    never = settle(book, Policy("sha_none", "SHA", "never"), context)
    rows.append(
        {
            "threshold_cents": None,
            "claims": never.claims,
            "repairs": never.repairs,
            "sender_bps": never.sender_bps,
            "supplier_bps": bps(never.supplier_cents, never.value_cents),
            "economic_bps": never.economic_bps,
        }
    )
    return rows


def _tolerance_sweep(book: Book, context: dict) -> list[dict]:
    rows = []
    for minimum in TOLERANCES:
        result = settle(
            book, Policy("sha_none", "SHA", "never"), context,
            tolerance_bps=TOLERANCE_BPS, tolerance_min=minimum,
        )
        rows.append(
            {
                "tolerance_min_cents": minimum,
                "claims": result.claims,
                "claim_share_pct": round(result.claims * 100 / result.invoices, 2),
                "ops_bps": bps(result.ops_cents, result.value_cents),
                "supplier_bps": bps(result.supplier_cents, result.value_cents),
                "economic_bps": result.economic_bps,
            }
        )
    return rows


def _comparisons(book: Book, results: dict[str, Result], sweep: list[dict]) -> dict:
    value = book.total_cents()
    sha, our, ben = results[HEADLINE], results[COMPARATOR], results["ben_all"]
    strict, repair50 = results["sha_repair_all"], results["sha_claim_50"]
    rule, cost = results["corridor_rule"], results["cost_rule"]
    oracle = results["oracle"]
    practical = [r for name, r in results.items() if name != "oracle"]
    best = min(practical, key=lambda r: r.economic_cents)
    claim_rows = [row for row in strict.rows if row.repaired]
    claim_median = sorted(row.shortfall_cents for row in claim_rows)[len(claim_rows) // 2] if claim_rows else 0
    prize = sha.economic_cents - oracle.economic_cents

    def capture(result: Result) -> float:
        return 0.0 if prize == 0 else round((sha.economic_cents - result.economic_cents) * 100 / prize, 2)

    return {
        "value_cents": value,
        "sha_sender_bps": sha.sender_bps,
        "our_sender_bps": our.sender_bps,
        "sha_economic_bps": sha.economic_bps,
        "our_economic_bps": our.economic_bps,
        "ben_economic_bps": ben.economic_bps,
        "sha_saves_sender_bps": round(our.sender_bps - sha.sender_bps, 3),
        "sha_supplier_bps": bps(sha.supplier_cents, value),
        "sha_claims": sha.claims,
        "sha_claim_share_pct": round(sha.claims * 100 / sha.invoices, 2),
        "strict_economic_bps": strict.economic_bps,
        "strict_above_our_bps": round(strict.economic_bps - our.economic_bps, 3),
        "claim_median_cents": claim_median,
        "max_claim_cents": max((row.shortfall_cents for row in sha.rows if row.claimed), default=0),
        "repair_fee_at_median_cents": our_fee(claim_median),
        "repair_all_cost_per_claim_cents": 0
        if not claim_rows
        else round(sum(row.economic_cents for row in claim_rows) / len(claim_rows)),
        "claim50_economic_bps": repair50.economic_bps,
        "best_economic_policy": best.policy,
        "best_economic_bps": best.economic_bps,
        "oracle_economic_bps": oracle.economic_bps,
        "oracle_prize_cents": prize,
        "oracle_gap_bps": round(best.economic_bps - oracle.economic_bps, 3),
        "corridor_rule_economic_bps": rule.economic_bps,
        "corridor_rule_capture_pct": capture(rule),
        "cost_rule_economic_bps": cost.economic_bps,
        "cost_rule_capture_pct": capture(cost),
        "cheapest_sender_policy": min(practical, key=lambda r: r.sender_total_cents).policy,
        "sweep_cheapest_index": min(range(len(sweep)), key=lambda i: sweep[i]["economic_bps"]),
    }


def _checks(book: Book, results: dict[str, Result], sweep: list[dict], seed, invoices, days) -> dict:
    again = generate(seed=seed, invoices=invoices, days=days)
    conservation = all(
        r.delivered_cents + r.shortfall_cents == r.value_cents for r in results.values()
    )
    partition = all(
        r.sender_total_cents
        == r.sender_fee_cents + r.repair_cents + r.repair_fee_cents + r.ops_cents
        and r.economic_cents == r.sender_total_cents + r.supplier_cents
        for r in results.values()
    )
    claim_rule = all(
        row.claimed == (row.shortfall_cents > row.tolerance_cents)
        for r in results.values()
        for row in r.rows
    )
    our_full = all(row.shortfall_cents == 0 for row in results["our_all"].rows)
    practical = [r for name, r in results.items() if name != "oracle"]
    sweep_repairs = [row["repairs"] for row in sweep]
    return {
        "conservation": conservation,
        "cost_partition": partition,
        "claim_rule_matches_tolerance": claim_rule,
        "our_delivers_full_value": our_full,
        "repair_control_binds": results["sha_claim_50"].repairs > 0
        and results["sha_claim_50"].declined > 0,
        "tolerance_absorbs_something": results["sha_none"].tolerated > 0,
        "oracle_is_a_lower_bound": results["oracle"].economic_cents
        <= min(r.economic_cents for r in practical),
        "book_rebuilds_identically": again.total_cents() == book.total_cents()
        and again.deductions_cents() == book.deductions_cents()
        and [inv.id for inv in again.invoices] == [inv.id for inv in book.invoices],
        "sweep_is_complete": len(sweep) == len(CLAIM_THRESHOLDS) + 1,
        "repairs_fall_as_the_threshold_rises": all(
            a >= b for a, b in zip(sweep_repairs, sweep_repairs[1:])
        ),
        "three_codes_are_priced": len({r.code for r in results.values() if r.code != "SHA"}) >= 2,
        "ben_and_sha_carry_the_same_money": results["ben_all"].economic_cents
        - results["sha_none"].economic_cents
        == results["ben_all"].ops_cents - results["sha_none"].ops_cents,
        "ben_moves_the_bill_off_the_sender": results["ben_all"].sender_total_cents
        < results["sha_none"].sender_total_cents,
    }


def build(seed: int = 20261126, invoices: int = 2_000, days: int = 90) -> dict:
    book = generate(seed=seed, invoices=invoices, days=days)
    milli = {code: _milli(value) for code, value in expected_bps(book).items()}
    winners = _winners(book)
    context = {"winners": winners, "milli": milli}
    results = {policy.name: settle(book, policy, context) for policy in policies()}
    sweep = _claim_sweep(book, context)

    return {
        "book": {
            "seed": book.seed,
            "days": book.days,
            "invoices": len(book.invoices),
            "value_cents": book.total_cents(),
            "deductions_cents": book.deductions_cents(),
            "deduction_bps": bps(book.deductions_cents(), book.total_cents()),
            "median_cents": sorted(inv.amount_cents for inv in book.invoices)[len(book.invoices) // 2],
        },
        "tariff": {
            "our_min_cents": 3_500,
            "our_bps": 28,
            "sha_min_cents": 1_000,
            "bank_bps": 8,
            "claim_ops_cents": CLAIM_OPS_CENTS,
            "tolerance_bps": TOLERANCE_BPS,
            "tolerance_min_cents": TOLERANCE_MIN_CENTS,
        },
        "corridors": _corridor_rows(book, milli),
        "policies": [_row(results[name]) for name in (p.name for p in policies())],
        "comparisons": _comparisons(book, results, sweep),
        "breakeven": _breakeven(book, milli),
        "claim_threshold_sweep": sweep,
        "tolerance_sweep": _tolerance_sweep(book, context),
        "checks": _checks(book, results, sweep, seed, invoices, days),
    }


def render_markdown(summary: dict) -> str:
    book = summary["book"]
    lines = [
        "# Correspondent charge codes bench",
        "",
        f"Synthetic book, seed {book['seed']}, {book['days']} days, {book['invoices']:,} invoices, "
        f"{usd(book['value_cents'])} instructed, {book['deduction_bps']} bps taken by the chains.",
        "",
        "| Policy | Claims | Repairs | Sender | Supplier | Economic | Sender bps | Economic bps |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["policies"]:
        lines.append(
            f"| {row['policy']} | {row['claims']} | {row['repairs']} | "
            f"{usd(row['sender_total_cents'])} | {usd(row['supplier_cents'])} | "
            f"{usd(row['economic_total_cents'])} | {row['sender_bps']:.2f} | {row['economic_bps']:.2f} |"
        )
    lines += [
        "",
        "| Corridor | Hops | Invoices | Value | Deduction bps | SHA bps | OUR bps | Cheaper |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["corridors"]:
        lines.append(
            f"| {row['corridor']} | {row['hops']} | {row['invoices']} | {usd(row['value_cents'])} | "
            f"{row['deduction_bps']:.2f} | {row['sha_bps']:.2f} | {row['our_bps']:.2f} | {row['cheaper']} |"
        )
    lines += [
        "",
        "| Claim threshold | Repairs | Claims | Sender bps | Supplier bps | Economic bps |",
        "|---|---|---|---|---|---|",
    ]
    for row in summary["claim_threshold_sweep"]:
        label = "never" if row["threshold_cents"] is None else usd(row["threshold_cents"])
        lines.append(
            f"| {label} | {row['repairs']} | {row['claims']} | {row['sender_bps']:.2f} | "
            f"{row['supplier_bps']:.2f} | {row['economic_bps']:.2f} |"
        )
    lines += [
        "",
        "| Supplier tolerance | Claims | Claim share | Ops bps | Economic bps |",
        "|---|---|---|---|---|",
    ]
    for row in summary["tolerance_sweep"]:
        lines.append(
            f"| {usd(row['tolerance_min_cents'])} | {row['claims']} | {row['claim_share_pct']:.2f}% | "
            f"{row['ops_bps']:.3f} | {row['economic_bps']:.2f} |"
        )
    return "\n".join(lines)


def summary_lines(summary: dict) -> list[str]:
    cmp = summary["comparisons"]
    return [
        f"book: {summary['book']['invoices']:,} invoices, {usd(cmp['value_cents'])}, "
        f"{summary['book']['deduction_bps']} bps taken",
        f"SHA: sender {cmp['sha_sender_bps']} bps, supplier {cmp['sha_supplier_bps']} bps, "
        f"economic {cmp['sha_economic_bps']} bps",
        f"OUR: sender and economic {cmp['our_economic_bps']} bps",
        f"best practical: {cmp['best_economic_policy']} {cmp['best_economic_bps']} bps, "
        f"oracle {cmp['oracle_economic_bps']} bps, prize {usd(cmp['oracle_prize_cents'])}",
    ]


def write_results(directory: Path | None = None, summary: dict | None = None) -> Path:
    """Write summary.json and summary.md.

    The default is resolved here, not bound at import, so a test that points the
    writer at a scratch directory really writes there.
    """
    target = RESULTS if directory is None else directory
    target.mkdir(parents=True, exist_ok=True)
    payload = build() if summary is None else summary
    (target / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (target / "summary.md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return target
