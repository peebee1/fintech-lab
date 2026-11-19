"""Bench: sweep the capture window and the tolerance, write committed results."""

from __future__ import annotations

import json
from pathlib import Path

from .book import Book, generate_book
from .policy import CEILING, DEFAULT, EXPIRY_SWEEP, TOLERANCE_SWEEP, TIERED, Policy
from .sim import Result, run

RESULTS = Path(__file__).resolve().parents[1] / "results"


def usd(cents: int) -> str:
    return f"{cents / 100:,.2f}"


def share(cents: int, total: int) -> float:
    return round(cents / total, 6) if total else 0.0


def arrival_profile(book: Book) -> list[dict]:
    """How much settlement value arrives after N days, independent of any policy."""
    buckets: dict[int, int] = {}
    for auth in book.auths:
        for capture in auth.captures:
            offset = capture.day - auth.approved_day
            buckets[offset] = buckets.get(offset, 0) + capture.cents
    total = sum(buckets.values())
    rows = []
    cumulative = 0
    for offset in sorted(buckets):
        cumulative += buckets[offset]
        rows.append(
            {
                "day_offset": offset,
                "cents": buckets[offset],
                "cumulative_cents": cumulative,
                "cumulative_share": share(cumulative, total),
            }
        )
    return rows


def build(seed: int = 20261119) -> dict:
    book = generate_book(seed)
    ceiling = run(book, CEILING, label="ceiling")

    expiry_sweep = [
        run(book, Policy(expiry_days=d, tolerance_bp=DEFAULT.tolerance_bp), label=f"expiry_{d}d")
        for d in EXPIRY_SWEEP
    ]
    tolerance_sweep = [
        run(book, Policy(expiry_days=DEFAULT.expiry_days, tolerance_bp=t), label=f"tolerance_{t}bp")
        for t in TOLERANCE_SWEEP
    ]
    overflow = [
        run(book, Policy(expiry_days=DEFAULT.expiry_days, tolerance_bp=DEFAULT.tolerance_bp, overflow=mode), label=f"overflow_{mode}")
        for mode in ("refuse", "cap")
    ]

    policy_compare = [
        run(book, Policy(expiry_days=7, tolerance_bp=DEFAULT.tolerance_bp), label="blanket_7d"),
        run(book, Policy(expiry_days=14, tolerance_bp=DEFAULT.tolerance_bp), label="blanket_14d"),
        run(book, Policy(expiry_days=21, tolerance_bp=DEFAULT.tolerance_bp), label="blanket_21d"),
        run(book, TIERED, label="tiered_by_class"),
        run(book, CEILING, label="ceiling"),
    ]

    tip_cents = sum(max(0, a.requested_cents - a.authorized_cents) for a in book.auths)

    profile = arrival_profile(book)
    total_value = book.requested_cents
    within_7 = next((r["cumulative_cents"] for r in profile if r["day_offset"] == 7), 0)
    within_14 = next((r["cumulative_cents"] for r in profile if r["day_offset"] == 14), 0)

    default = expiry_sweep[EXPIRY_SWEEP.index(DEFAULT.expiry_days)]
    longest = expiry_sweep[-1]

    payload = {
        "synthetic": True,
        "seed": seed,
        "book": {
            "authorisations": len(book.auths),
            "authorised_cents": book.authorized_cents,
            "requested_cents": book.requested_cents,
            "horizon_days": book.horizon,
            "by_kind": book.by_kind(),
            "never_captured": sum(1 for a in book.auths if not a.captures),
            "tip_cents": tip_cents,
        },
        "ceiling": ceiling.as_dict(),
        "expiry_sweep": [r.as_dict() for r in expiry_sweep],
        "tolerance_sweep": [r.as_dict() for r in tolerance_sweep],
        "overflow_compare": [r.as_dict() for r in overflow],
        "policy_compare": [r.as_dict() for r in policy_compare],
        "arrival_profile": profile,
        "headline": {
            "default_expiry_days": DEFAULT.expiry_days,
            "default_capture_rate": round(default.capture_rate, 6),
            "default_refused_expired_cents": default.refused_expired_cents,
            "longest_expiry_days": longest.policy.expiry_days,
            "longest_capture_rate": round(longest.capture_rate, 6),
            "frozen_cents_days_default": default.frozen_funds_cents_days,
            "frozen_cents_days_longest": longest.frozen_funds_cents_days,
            "value_within_7_days_share": share(within_7, total_value),
            "value_within_14_days_share": share(within_14, total_value),
            "tolerance_refused_at_0bp_cents": tolerance_sweep[0].refused_tolerance_cents,
            "tolerance_refused_at_1500bp_cents": tolerance_sweep[TOLERANCE_SWEEP.index(1500)].refused_tolerance_cents,
            "tiered_capture_rate": round(policy_compare[3].capture_rate, 6),
            "tiered_frozen_cents_days": policy_compare[3].frozen_funds_cents_days,
            "blanket_21_capture_rate": round(policy_compare[2].capture_rate, 6),
            "blanket_21_frozen_cents_days": policy_compare[2].frozen_funds_cents_days,
            "tip_cents": tip_cents,
            "capture_mode_refused_cents": overflow[0].refused_tolerance_cents,
            "cap_mode_refused_cents": overflow[1].refused_tolerance_cents,
        },
    }
    return payload


def render_markdown(payload: dict) -> str:
    book = payload["book"]
    head = payload["headline"]
    lines = [
        "# auth-holds results",
        "",
        "Generated by `python -m authholds.cli bench`. Synthetic book, seed "
        f"{payload['seed']}, {book['authorisations']} authorisations, USD "
        f"{usd(book['requested_cents'])} of requested settlement value, USD "
        f"{usd(book['tip_cents'])} of tips above the authorisation.",
        "",
        "## Policy comparison, tolerance 15 percent",
        "",
        "| Policy | Captured USD | Capture rate | Refused expired USD | Frozen funds USD days |",
        "|---|---|---|---|---|",
    ]
    for row in payload["policy_compare"]:
        lines.append(
            f"| {row['label']} | {usd(row['captured_cents'])} | {row['capture_rate'] * 100:.1f}% | "
            f"{usd(row['refused_expired_cents'])} | {usd(row['frozen_funds_cents_days'])} |"
        )

    lines += [
        "",
        "## Expiry sweep, tolerance 15 percent, over limit captures refused",
        "",
        "| Hold days | Captures | Captured USD | Capture rate | Refused expired USD | Frozen funds USD days |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["expiry_sweep"]:
        lines.append(
            f"| {row['expiry_days']} | {row['captures_accepted']} | {usd(row['captured_cents'])} | "
            f"{row['capture_rate'] * 100:.1f}% | {usd(row['refused_expired_cents'])} | "
            f"{usd(row['frozen_funds_cents_days'])} |"
        )

    lines += [
        "",
        "## Tolerance sweep, 7 day hold, over limit captures refused",
        "",
        "| Tolerance | Captured USD | Capture rate | Refused over limit USD | Frozen funds USD days |",
        "|---|---|---|---|---|",
    ]
    for row in payload["tolerance_sweep"]:
        lines.append(
            f"| {row['tolerance_bp'] / 100:.0f}% | {usd(row['captured_cents'])} | "
            f"{row['capture_rate'] * 100:.1f}% | {usd(row['refused_tolerance_cents'])} | "
            f"{usd(row['frozen_funds_cents_days'])} |"
        )

    lines += [
        "",
        "## Over limit handling, 7 day hold, 15 percent tolerance",
        "",
        "| Mode | Captured USD | Refused over limit USD | Frozen funds USD days |",
        "|---|---|---|---|",
    ]
    for row in payload["overflow_compare"]:
        lines.append(
            f"| {row['overflow']} | {usd(row['captured_cents'])} | "
            f"{usd(row['refused_tolerance_cents'])} | {usd(row['frozen_funds_cents_days'])} |"
        )

    lines += [
        "",
        "## Settlement arrival, before any policy",
        "",
        "| Day offset | Value USD | Cumulative share |",
        "|---|---|---|",
    ]
    for row in payload["arrival_profile"]:
        if row["day_offset"] in {0, 1, 3, 5, 7, 10, 14, 21, 28}:
            lines.append(
                f"| {row['day_offset']} | {usd(row['cents'])} | {row['cumulative_share'] * 100:.1f}% |"
            )

    lines += [
        "",
        "## Headline",
        "",
        f"- Default 7 day hold captures {head['default_capture_rate'] * 100:.1f}% of requested value and refuses USD "
        f"{usd(head['default_refused_expired_cents'])} past expiry.",
        f"- A {head['longest_expiry_days']} day hold captures {head['longest_capture_rate'] * 100:.1f}% and holds USD "
        f"{usd(head['frozen_cents_days_longest'])} of customer funds days against USD "
        f"{usd(head['frozen_cents_days_default'])} at 7 days.",
        f"- Value settling within 7 days: {head['value_within_7_days_share'] * 100:.1f}%, within 14 days: "
        f"{head['value_within_14_days_share'] * 100:.1f}%.",
        f"- Tiered windows capture {head['tiered_capture_rate'] * 100:.1f}% and hold USD "
        f"{usd(head['tiered_frozen_cents_days'])} of funds days against "
        f"{head['blanket_21_capture_rate'] * 100:.1f}% and USD {usd(head['blanket_21_frozen_cents_days'])} "
        "for a blanket 21 day window.",
        f"- Refusing an over limit capture loses USD {usd(head['capture_mode_refused_cents'])}; settling what fits "
        f"loses USD {usd(head['cap_mode_refused_cents'])}.",
        "",
    ]
    return "\n".join(lines)


def write_results(directory: Path | None = None, payload: dict | None = None) -> dict:
    """Resolve the default inside the call, so a test can point it at a temp dir."""
    target = RESULTS if directory is None else Path(directory)
    data = build() if payload is None else payload
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (target / "summary.md").write_text(render_markdown(data), encoding="utf-8")
    return data


def summarise(payload: dict) -> list[str]:
    head = payload["headline"]
    return [
        f"book USD {usd(payload['book']['requested_cents'])}, {payload['book']['authorisations']} authorisations",
        f"7 day hold: capture rate {head['default_capture_rate'] * 100:.1f}%, refused expired USD "
        f"{usd(head['default_refused_expired_cents'])}",
        f"{head['longest_expiry_days']} day hold: capture rate {head['longest_capture_rate'] * 100:.1f}%, frozen funds USD "
        f"{usd(head['frozen_cents_days_longest'])} days",
    ]


def compare(results: list[Result]) -> list[dict]:
    return [r.as_dict() for r in results]
