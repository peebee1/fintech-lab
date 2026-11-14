"""What a sealed ledger refuses, and what the stored balance baseline lets through.

Every number in results/ comes from this module. The bench fails rather than emit an empty
table: if the baseline does not drift, or a named refusal never fires, there is nothing to
compare and the run is a defect.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from . import book as bookmod
from . import inr
from .entry import Line
from .ledger import Ledger, Refusal, period_of
from .naive import MutableLedger

RESULTS = Path(__file__).resolve().parent.parent / "results"
FIXED_NOW = datetime(2026, 5, 20, 9, 30, tzinfo=timezone.utc)
SEED = 7
MONTHS = 6
PER_MONTH = 40
CLOSE_COUNT = 4
ADJUSTMENT_DAY = date(2026, 5, 15)
FEE_MINOR = 185_000        # 1,850.00 bank fee found after March was closed
RECLASS_MINOR = 500_000    # 5,000.00 moved from fee revenue to tax payable
SHORT_MINOR = 100_000      # a posting 1,000.00 short of zero
TAMPER_MINOR = 2_500_000   # 25,000.00 written into one January line out of band
RULES = ("ClosedPeriod", "NoAmend", "Unbalanced")


def _with_delta(lines: Iterable[Line], account: str, amount: int) -> list[Line]:
    return [
        Line(line.account, line.amount_minor + amount) if line.account == account else line
        for line in lines
    ]


def _drift_block(drifts: dict[str, dict[str, int]]) -> dict:
    return {
        "periods_drifted": sum(1 for drift in drifts.values() if drift),
        "absolute_minor": sum(abs(value) for drift in drifts.values() for value in drift.values()),
        "fee_revenue_minor": sum(drift.get("fee_revenue", 0) for drift in drifts.values()),
        "per_period": {period: drifts[period] for period in sorted(drifts)},
    }


def run(directory: Path | str | None = None, seed: int = SEED, months: int = MONTHS, per_month: int = PER_MONTH) -> dict:
    out_dir = RESULTS if directory is None else Path(directory)
    clock = lambda: FIXED_NOW
    book = bookmod.build(seed=seed, months=months, per_month=per_month)

    with tempfile.TemporaryDirectory(prefix="ledgerclose-") as tmp:
        sealed_dir = Path(tmp) / "sealed"
        sealed = Ledger(sealed_dir, clock=clock)
        for txn in book:
            sealed.post(txn.lines, txn.business_date, idempotency_key=txn.label)

        baseline = MutableLedger(clock=clock)
        for txn in book:
            baseline.post(txn.lines, txn.business_date, idempotency_key=txn.label)

        periods = book.periods
        closed = periods[:CLOSE_COUNT]
        for period in closed:
            sealed.close(period)
            baseline.close(period)

        # Baseline check: before any event, both agree with what they reported.
        clean_drift = {period: sealed.drift(period) for period in closed}
        if any(clean_drift.values()):
            raise AssertionError("sealed ledger drifted before any event was attempted")
        if not all(baseline.close_reproduces(period) for period in closed):
            raise AssertionError("baseline close did not reproduce before any event")

        rules: dict[str, int] = {}

        def attempt(action) -> None:
            try:
                action()
            except Refusal as refusal:
                rules[refusal.rule] = rules.get(refusal.rule, 0) + 1

        # Event 1: a bank fee discovered after March closed, dated back into March.
        fee_lines = [Line("bank_fees", FEE_MINOR), Line("cash", -FEE_MINOR)]
        attempt(lambda: sealed.post(fee_lines, date(2026, 3, 31), idempotency_key="late-bank-fee"))
        sealed.post(fee_lines, ADJUSTMENT_DAY, idempotency_key="late-bank-fee")
        baseline.post(fee_lines, date(2026, 3, 31), idempotency_key="late-bank-fee")

        # Event 2: an operator reclassifies 5,000 of January fee revenue to tax payable.
        january = sealed.entries_in(closed[0])[0]
        baseline_january = baseline.postings[0]
        if baseline_january["business_date"] != january.business_date:
            raise AssertionError("baseline and sealed journals are not aligned")
        corrected = _with_delta(_with_delta(january.lines, "fee_revenue", RECLASS_MINOR), "tax_payable", -RECLASS_MINOR)
        attempt(lambda: sealed.amend(january.entry_id, corrected))
        sealed.reverse(january.entry_id, ADJUSTMENT_DAY)
        sealed.post(corrected, ADJUSTMENT_DAY, kind="adjustment", idempotency_key="reclass-january")
        baseline.amend(baseline_january["id"], corrected)

        # Event 3: the client retries a payment it already sent, same idempotency key.
        first_open = periods[CLOSE_COUNT]
        retry = max(
            (txn for txn in book if txn.kind == "payment" and period_of(txn.business_date) == first_open),
            key=lambda txn: txn.gross_minor,
        )
        open_before = baseline.control_totals(first_open)
        journal_before = len(sealed.journal)
        sealed.post(retry.lines, retry.business_date, idempotency_key=retry.label)
        sealed_replay_appended = len(sealed.journal) - journal_before
        baseline.post(retry.lines, retry.business_date, idempotency_key=retry.label)
        open_after = baseline.control_totals(first_open)

        # Event 4: a posting whose lines do not sum to zero, once backdated and once live.
        short_lines = [Line("cash", 500_000), Line("fee_revenue", -400_000)]
        attempt(lambda: sealed.post(short_lines, date(2026, 2, 20), idempotency_key="short-backdated"))
        baseline.post(short_lines, date(2026, 2, 20), idempotency_key="short-backdated")
        attempt(lambda: sealed.post(short_lines, ADJUSTMENT_DAY, idempotency_key="short-live"))
        baseline.post(short_lines, ADJUSTMENT_DAY, idempotency_key="short-live")

        for rule in RULES:
            if not rules.get(rule):
                raise AssertionError(f"refusal {rule} never fired: the comparison would be empty")

        sealed_drift = _drift_block({period: sealed.drift(period) for period in closed})
        baseline_drift = _drift_block({period: baseline.drift(period) for period in closed})
        if sealed_drift["periods_drifted"] != 0:
            raise AssertionError("sealed ledger drifted into a closed period")
        if baseline_drift["periods_drifted"] == 0:
            raise AssertionError("baseline did not drift: nothing to measure")

        sealed_closes_ok = sum(1 for check in sealed.verify_all_closes() if check.ok)
        baseline_closes_ok = sum(1 for period in closed if baseline.close_reproduces(period))
        baseline_net_after_events = baseline.net_minor()
        baseline_balanced_after_events = sum(1 for period in periods if baseline.trial_balance(period)["balanced"])

        # Event 5: someone edits the sealed journal on disk, out of band.
        journal_path = sealed.entries.path
        raw = journal_path.read_text(encoding="utf-8").splitlines()
        record = json.loads(raw[january.seq - 1])
        record["lines"] = [
            [account, amount - TAMPER_MINOR] if account == "fee_revenue" else [account, amount]
            for account, amount in record["lines"]
        ]
        raw[january.seq - 1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
        journal_path.write_text("\n".join(raw) + "\n", encoding="utf-8")

        after_tamper = Ledger(sealed_dir, clock=clock)
        chain = after_tamper.verify()
        closes_after_tamper = after_tamper.verify_all_closes()
        tampered_period_drift = after_tamper.drift(closed[0])

        # The same out of band edit against the baseline: there is nothing to check it against.
        baseline.postings[0]["lines"] = [
            [account, amount - TAMPER_MINOR] if account == "fee_revenue" else [account, amount]
            for account, amount in baseline.postings[0]["lines"]
        ]

        sealed_trial = [sealed.trial_balance(period) for period in periods]
        chain_clean = sealed.verify()

        payload = {
            "artifact": "ledger-close",
            "as_of": FIXED_NOW.isoformat().replace("+00:00", "Z"),
            "seed": seed,
            "book": {
                "months": months,
                "entries": len(book),
                "counts": book.counts,
                "gross_minor": book.gross_minor,
                "average_payment_minor": round(book.gross_minor / max(1, book.payments)),
            },
            "closed_periods": closed,
            "sealed": {
                "journal_entries": len(sealed.journal),
                "chain_before_tamper": {"ok": chain_clean.ok, "checked": chain_clean.checked},
                "chain": {"ok": chain.ok, "checked": chain.checked, "broken_seq": chain.broken_seq, "reason": chain.reason},
                "closed_period_drift": sealed_drift,
                "closes_reproducing_before_tamper": sealed_closes_ok,
                "closes_reproducing_after_tamper": sum(1 for check in closes_after_tamper if check.ok),
                "failing_closes": [check.period for check in closes_after_tamper if not check.ok],
                "tamper_drift_minor": sum(abs(value) for value in tampered_period_drift.values()),
                "refusals": dict(sorted(rules.items())),
                "replay_entries_appended": sealed_replay_appended,
                "balanced_periods": sum(1 for trial in sealed_trial if trial.balanced),
                "periods_tested": len(periods),
                "net_minor": sum(trial.net_minor for trial in sealed_trial),
                "open_period_fee_revenue_minor": sealed.control_totals(first_open).get("fee_revenue", 0),
            },
            "baseline": {
                "closed_period_drift": baseline_drift,
                "closes_reproducing": baseline_closes_ok,
                "duplicate_fee_minor": open_after.get("fee_revenue", 0) - open_before.get("fee_revenue", 0),
                "net_minor_after_events": baseline_net_after_events,
                "balanced_periods_after_events": baseline_balanced_after_events,
                "periods_tested": len(periods),
                "tamper_detected": 1 if not baseline.verify()["ok"] else 0,
                "tamper_drift_minor": sum(abs(value) for value in baseline.drift(closed[0]).values()),
                "net_minor_after_tamper": baseline.net_minor(),
            },
        }

    write_results(payload, out_dir)
    return payload


def write_results(payload: dict, directory: Path | str | None = None) -> Path:
    target = RESULTS if directory is None else Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (target / "summary.md").write_text(_render_markdown(payload), encoding="utf-8")
    return target


def _table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out)


def _render_markdown(payload: dict) -> str:
    sealed = payload["sealed"]
    baseline = payload["baseline"]
    book = payload["book"]
    periods = payload["closed_periods"]
    drift_rows = []
    for period in periods:
        drift_rows.append([
            period,
            _cell(sealed["closed_period_drift"]["per_period"].get(period, {})),
            _cell(baseline["closed_period_drift"]["per_period"].get(period, {})),
        ])
    refusal_rows = [[rule, str(count)] for rule, count in sealed["refusals"].items()]

    return "\n".join([
        "# ledger-close results",
        "",
        f"Bench clock: {payload['as_of']}. Seed {payload['seed']}. Synthetic book, no real data.",
        "",
        f"- book transactions: {book['entries']} "
        f"({', '.join(f'{count} {kind}' for kind, count in book['counts'].items())})",
        f"- gross processed: {inr(book['gross_minor'])}",
        f"- average payment: {inr(book['average_payment_minor'])}",
        f"- closed periods: {', '.join(periods)}",
        "",
        "## Closed period drift, reported total versus recomputed total",
        "",
        _table(["period", "sealed drift", "baseline drift"], drift_rows),
        "",
        "## Refusals fired by the sealed ledger",
        "",
        _table(["rule", "count"], refusal_rows),
        "",
        f"Idempotent replay appended {sealed['replay_entries_appended']} entries. "
        f"The baseline accepted the same retry and credited {inr(abs(baseline['duplicate_fee_minor']))} of fee revenue twice.",
        "",
        "## Proofs",
        "",
        _table(["check", "sealed", "baseline"], [
            ["closes reproducing after the events", f"{sealed['closes_reproducing_before_tamper']}/{len(periods)}", f"{baseline['closes_reproducing']}/{len(periods)}"],
            ["periods balanced after the events", f"{sealed['balanced_periods']}/{sealed['periods_tested']}", f"{baseline['balanced_periods_after_events']}/{baseline['periods_tested']}"],
            ["book nets to zero after the events", inr(sealed["net_minor"]), inr(baseline["net_minor_after_events"])],
            ["out of band edit detected", "yes" if not sealed["chain"]["ok"] else "no", "yes" if baseline["tamper_detected"] else "no"],
        ]),
        "",
        f"The edited entry breaks the chain at seq {sealed['chain']['broken_seq']} "
        f"({sealed['chain']['reason']}) and moves {inr(sealed['tamper_drift_minor'])} of January revenue. "
        f"Closes that no longer reproduce: {', '.join(sealed['failing_closes']) or 'none'}.",
        "",
        "Reproduce: `PYTHONPATH=. uv run python -m ledgerclose.cli bench` from this directory.",
        "",
    ])


def _cell(drift: dict[str, int]) -> str:
    if not drift:
        return "none"
    return ", ".join(f"{account} {inr(amount)}" for account, amount in sorted(drift.items()))
