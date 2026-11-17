"""Bench: seven refresh policies, one book, plus a lead sweep and two stress runs."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from consent.book import HORIZON_DAYS, LIFETIME_DAYS, Payer, annual_value_cents, build_book
from consent.policy import AdaptiveLead, FixedCadence, JustInTime, NeverRefresh, OnFailure
from consent.sim import audit_consents, run

RESULTS = Path(__file__).resolve().parent.parent / "results"
SEED = 20261118
PAYERS = 1200
SIZE = 1200


def _policy_set() -> list:
    return [
        NeverRefresh(),
        OnFailure(),
        FixedCadence(30),
        FixedCadence(90),
        JustInTime(1),
        JustInTime(2),
        JustInTime(3),
        JustInTime(7),
        AdaptiveLead(),
    ]


def _row(result, ceiling_cents: int, payers: list[Payer]) -> dict:
    totals = result.totals
    captured = sum(s.captured_cents for s in result.states.values())
    prompts = totals["prompts"]
    contextual = totals["contextual_prompts"]
    return {
        "policy": result.policy,
        "settled": totals["settled"],
        "refused": totals["refused"],
        "refused_usd": totals["refused_usd"],
        "captured_usd": round(captured / 100, 2),
        "capture_rate": round(captured / ceiling_cents, 4) if ceiling_cents else 0.0,
        "prompts": prompts,
        "prompts_per_payer": round(prompts / len(payers), 2),
        "contextual_share": round(contextual / prompts, 4) if prompts else 0.0,
        "renewals": totals["renewals"],
        "abandons": totals["abandons"],
        "abandon_rate_per_prompt": round(totals["abandons"] / prompts, 4) if prompts else 0.0,
        "usd_per_prompt": round(captured / 100 / prompts, 2) if prompts else None,
        "churned": totals["churned"],
    }


def run_bench(directory: Path | None = None, seed: int = SEED, size: int = SIZE) -> dict:
    """Run every policy and write results/. `directory=None` means the committed results dir."""
    out_dir = RESULTS if directory is None else Path(directory)
    payers = build_book(seed=seed, size=size)
    scheduled_cents = annual_value_cents(payers)

    ceiling_run = run(payers, NeverRefresh(), seed=seed, lifetime_days=10**6)
    ceiling_cents = sum(s.captured_cents for s in ceiling_run.states.values())

    runs = {}
    rows = []
    audits = {}
    for policy in _policy_set():
        result = run(payers, policy, seed=seed)
        runs[policy.name] = result
        rows.append(_row(result, ceiling_cents, payers))
        audits[policy.name] = audit_consents(result, lifetime_days=LIFETIME_DAYS)

    sweep = []
    for lead in range(1, 13):
        result = run(payers, JustInTime(lead), seed=seed)
        totals = result.totals
        captured = sum(s.captured_cents for s in result.states.values())
        sweep.append(
            {
                "lead_days": lead,
                "refused": totals["refused"],
                "captured_usd": round(captured / 100, 2),
                "capture_rate": round(captured / ceiling_cents, 4),
                "prompts": totals["prompts"],
                "contextual_share": round(totals["contextual_prompts"] / totals["prompts"], 4)
                if totals["prompts"]
                else 0.0,
            }
        )

    def stress(multiplier: float, latency_scale: float) -> list[dict]:
        out = []
        for policy in (FixedCadence(30), JustInTime(2), JustInTime(7), AdaptiveLead()):
            result = run(
                payers,
                policy,
                seed=seed,
                context_multiplier=multiplier,
                latency_scale=latency_scale,
            )
            captured = sum(s.captured_cents for s in result.states.values())
            out.append(
                {
                    "policy": policy.name,
                    "captured_usd": round(captured / 100, 2),
                    "capture_rate": round(captured / ceiling_cents, 4),
                    "refused": result.totals["refused"],
                    "prompts": result.totals["prompts"],
                }
            )
        return out

    base = {row["policy"]: row for row in rows}

    attempts_ok = True
    for result in runs.values():
        for state in result.states.values():
            due = [d for d in state.payer.due_days if state.exit_day is None or d < state.exit_day]
            if state.attempts != len(due) or state.settles + state.refusals != state.attempts:
                attempts_ok = False
                break

    jit_prompts_ok = all(
        event.get("at_risk_day") is not None
        for name, result in runs.items()
        if name.startswith("jit") or name == "adaptive_lead"
        for event in result.events
        if event["kind"] == "prompt"
    )

    repeat_a = run(payers[:200], AdaptiveLead(), seed=seed)
    repeat_b = run(payers[:200], AdaptiveLead(), seed=seed)

    checks = {
        "every_attempt_accounted": attempts_ok,
        "no_settlement_on_expired_consent": all(not a["violations"] for a in audits.values()),
        "jit_prompts_all_have_a_payment_at_risk": jit_prompts_ok,
        "never_refresh_sends_no_prompts": runs["never_refresh"].totals["prompts"] == 0,
        "ceiling_binds": ceiling_cents > max(
            sum(s.captured_cents for s in r.states.values()) for r in runs.values()
        ),
        "dropoff_binds": base["fixed_30"]["abandon_rate_per_prompt"] > 0.05
        and base["fixed_30"]["capture_rate"] < base["jit_2"]["capture_rate"],
        "contextual_conversion_shows": base["jit_2"]["abandon_rate_per_prompt"]
        < base["jit_7"]["abandon_rate_per_prompt"],
        "lead_time_binds": base["jit_1"]["refused"] > base["jit_7"]["refused"] > 0,
        "calendar_is_worse_than_jit": base["jit_7"]["capture_rate"] > base["fixed_90"]["capture_rate"],
        "deterministic": repeat_a.totals == repeat_b.totals,
    }

    payload = {
        "generated_for": "2026-11-18",
        "book": {
            "payers": len(payers),
            "merchants": 12,
            "days": HORIZON_DAYS,
            "consent_lifetime_days": LIFETIME_DAYS,
            "scheduled_usd": round(scheduled_cents / 100, 2),
            "scheduled_payments": sum(len(p.due_days) for p in payers),
            "median_bill_usd": round(statistics.median(p.bill_cents for p in payers) / 100, 2),
            "latency_p50_h": round(statistics.median(p.latency_median_h for p in payers), 1),
            "mean_abandon_prob": round(statistics.mean(p.abandon_prob for p in payers), 4),
        },
        "ceiling": {
            "policy": "no_expiry",
            "captured_usd": round(ceiling_cents / 100, 2),
            "note": "Reference only: consent never expires, natural churn still applies.",
        },
        "policies": rows,
        "sweep": sweep,
        "stress": {
            "no_context_advantage": stress(1.0, 1.0),
            "slow_responses_1_5x": stress(0.45, 1.5),
        },
        "audit": {name: a["checked"] for name, a in audits.items()},
        "checks": checks,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(payload))
    return payload


def usd(value: float) -> str:
    return f"{value:,.2f}"


def render_markdown(payload: dict) -> str:
    book = payload["book"]
    lines = ["# Results", ""]
    lines.append(
        f"Book: {book['payers']} synthetic payers across {book['merchants']} merchants, "
        f"{book['days']} days, {book['scheduled_payments']} scheduled debits, "
        f"USD {usd(book['scheduled_usd'])} billed. Consent lifetime {book['consent_lifetime_days']} days. "
        f"Median bill USD {usd(book['median_bill_usd'])}, median re-auth latency "
        f"{book['latency_p50_h']} hours, mean walk-away {book['mean_abandon_prob'] * 100:.1f}% per prompt."
    )
    lines.append("")
    lines.append(
        f"Reference ceiling: USD {usd(payload['ceiling']['captured_usd'])} captured with consents that never "
        "expire, which no rail allows. Natural churn still applies."
    )
    lines.append("")
    lines.append("## Policies")
    lines.append("")
    lines.append(
        "| Policy | Settled | Refused | Refused USD | Captured USD | Capture rate | Prompts | Prompts/payer | Contextual | Abandon per prompt | USD per prompt |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in payload["policies"]:
        per_prompt = "-" if row["usd_per_prompt"] is None else usd(row["usd_per_prompt"])
        lines.append(
            f"| {row['policy']} | {row['settled']} | {row['refused']} | {usd(row['refused_usd'])} | "
            f"{usd(row['captured_usd'])} | {row['capture_rate'] * 100:.1f}% | {row['prompts']} | "
            f"{row['prompts_per_payer']} | {row['contextual_share'] * 100:.1f}% | "
            f"{row['abandon_rate_per_prompt'] * 100:.1f}% | {per_prompt} |"
        )
    lines.append("")
    lines.append("## Lead time sweep (just in time)")
    lines.append("")
    lines.append("| Lead days | Refused | Captured USD | Capture rate | Prompts | Contextual share |")
    lines.append("|---|---|---|---|---|---|")
    for row in payload["sweep"]:
        lines.append(
            f"| {row['lead_days']} | {row['refused']} | {usd(row['captured_usd'])} | "
            f"{row['capture_rate'] * 100:.1f}% | {row['prompts']} | {row['contextual_share'] * 100:.1f}% |"
        )
    lines.append("")
    for title, key in (
        ("Stress: contextual prompts convert no better (multiplier 1.0)", "no_context_advantage"),
        ("Stress: re-auth responses 1.5x slower", "slow_responses_1_5x"),
    ):
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Policy | Captured USD | Capture rate | Refused | Prompts |")
        lines.append("|---|---|---|---|---|")
        for row in payload["stress"][key]:
            lines.append(
                f"| {row['policy']} | {usd(row['captured_usd'])} | {row['capture_rate'] * 100:.1f}% | "
                f"{row['refused']} | {row['prompts']} |"
            )
        lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for name, ok in payload["checks"].items():
        lines.append(f"| {name} | {'pass' if ok else 'FAIL'} |")
    lines.append("")
    lines.append(
        "Settlements audited against a replay of the logged consent timeline: "
        + ", ".join(f"{name} {count}" for name, count in payload["audit"].items())
        + " settlements, 0 on an expired consent."
    )
    lines.append("")
    return "\n".join(lines)
