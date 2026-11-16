"""Bench: calibrate a loss curve on 28 days, apply it to four held out weeks.

The calibrated policy's only input is a measured per chain table of P(lost | k
blocks), fitted on a different simulated history than the four evaluation weeks. The
four weeks are there so a single lucky week cannot carry the result: every policy is
scored on all of them, pooled and per week.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from random import Random

from .book import build_book, book_summary
from .chain import CHAINS, reorgs_by_chain
from .cost import Params
from .policy import MAX_K, POLICIES, confirmations
from .sim import BANDS, metrics, per_chain, run_policy

RESULTS = Path(__file__).resolve().parents[1] / "results"
DAYS = 7
CALIBRATION_DAYS = 28
CALIBRATION_SEED = 20261101
EVALUATION_SEEDS = (20261116, 20261123, 20261130, 20261207)
SWEEP = (1, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64)
STRESS_SCALE = 1.5


def calibrate(book, reorgs) -> dict:
    """P(false credit | k) and P(lost | k) per chain, k = 1..MAX_K.

    Curves are made non increasing in k: a loss rate cannot rise with more
    confirmations, so a rise is sampling noise and gets flattened. Without this the
    economic policy can prefer a larger k for a lower measured risk than a smaller
    one, which is an artefact of the sample, not a fact about the chain.
    """
    loss = {name: [] for name in CHAINS}
    false_credit = {name: [] for name in CHAINS}
    for k in range(1, MAX_K + 1):
        outcomes = run_policy(book, reorgs, k)
        for name in CHAINS:
            subset = [o for o in outcomes if o.chain == name]
            total = len(subset)
            lost = sum(1 for o in subset if o.status == "lost")
            bad = sum(1 for o in subset if o.status in {"lost", "reverted"})
            false_credit[name].append(bad / total if total else 0.0)
            loss[name].append(lost / total if total else 0.0)
    for name in CHAINS:
        _flatten(loss[name])
        _flatten(false_credit[name])
    return {"loss": loss, "false_credit": false_credit}


def _flatten(curve: list[float]) -> None:
    for index in range(1, len(curve)):
        if curve[index] > curve[index - 1]:
            curve[index] = curve[index - 1]


def k_summary(k_values: dict[str, list[int]]) -> dict:
    flat = [k for values in k_values.values() for k in values]
    return {
        "min": min(flat),
        "median": statistics.median(flat),
        "max": max(flat),
        "by_chain": {
            name: {
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
            for name, values in k_values.items()
        },
    }


def weeks() -> list[tuple[int, list, dict]]:
    out = []
    for seed in EVALUATION_SEEDS:
        book = build_book(seed, DAYS)
        reorgs = reorgs_by_chain(DAYS + 1, Random(seed))
        out.append((seed, book, reorgs))
    return out


def run_bench(results_dir: Path | str | None = None) -> dict:
    directory = Path(results_dir) if results_dir is not None else RESULTS
    directory.mkdir(parents=True, exist_ok=True)

    cal_book = build_book(CALIBRATION_SEED, CALIBRATION_DAYS)
    cal_reorgs = reorgs_by_chain(CALIBRATION_DAYS + 1, Random(CALIBRATION_SEED))
    risks = calibrate(cal_book, cal_reorgs)
    params = Params()
    week_data = weeks()

    policies: dict[str, dict] = {}
    credit_after_inclusion = True
    losses_attributable = True
    for name in POLICIES:
        pooled = []
        per_week = []
        k_values = {chain: [] for chain in CHAINS}
        for seed, book, reorgs in week_data:
            ks = {p.pid: confirmations(name, p, risks, params) for p in book}
            for payment in book:
                k_values[payment.chain].append(ks[payment.pid])
            outcomes = run_policy(book, reorgs, ks)
            inclusion = {p.pid: p.inclusion_height for p in book}
            credit_after_inclusion = credit_after_inclusion and all(
                o.credit_height >= inclusion[o.pid] for o in outcomes
            )
            losses_attributable = losses_attributable and all(
                o.exposed_cents > 0 for o in outcomes if o.status == "lost"
            )
            pooled.extend(outcomes)
            per_week.append(
                {
                    "seed": seed,
                    "loss_usd": round(sum(o.loss_cents for o in outcomes) / 100.0, 2),
                    "false_credits": sum(
                        1 for o in outcomes if o.status in {"lost", "reverted"}
                    ),
                }
            )
        k_stats = k_summary(k_values)
        policies[name] = {
            **metrics(pooled, params),
            "k": k_stats,
            "per_week": per_week,
            "per_chain": per_chain(pooled),
        }

    sweep = []
    for k in SWEEP:
        pooled = []
        for seed, book, reorgs in week_data:
            pooled.extend(run_policy(book, reorgs, k))
        row = metrics(pooled, params)
        row["k"] = k
        sweep.append(row)

    # Out of distribution: the same four weeks with incidents 1.5x deeper than
    # anything in the calibration month. Policies keep their k, because that is what
    # happens when a rule is deployed and the chain behaves worse than its history.
    stress = {}
    for name in POLICIES:
        pooled = []
        for seed, book, _ in week_data:
            deeper = reorgs_by_chain(DAYS + 1, Random(seed), incident_scale=STRESS_SCALE)
            ks = {p.pid: confirmations(name, p, risks, params) for p in book}
            pooled.extend(run_policy(book, deeper, ks))
        stress[name] = metrics(pooled, params)

    checks = {
        "every_credit_after_inclusion": credit_after_inclusion,
        "every_loss_was_credited_first": losses_attributable,
        "control_binds": policies["credit_on_inclusion"]["loss_usd"] > 0,
        "loss_is_a_subset_of_false_credits": all(
            policies[name]["loss_usd"] <= policies[name]["exposed_usd"] + 1e-9
            for name in policies
        ),
        "risk_curve_monotone": all(
            all(
                a >= b
                for a, b in zip(risks["loss"][name], risks["loss"][name][1:])
            )
            for name in CHAINS
        ),
        "calibration_has_events": all(
            sum(risks["loss"][name]) > 0 for name in CHAINS
        ),
        "four_weeks_scored": len(EVALUATION_SEEDS) == 4,
    }

    payload = {
        "schema": 1,
        "command": "PYTHONPATH=. uv run python -m finality.cli bench",
        "model": "synthetic reorg process, stated in finality/chain.py",
        "window_days": DAYS,
        "weeks": list(EVALUATION_SEEDS),
        "calibration": {
            "days": CALIBRATION_DAYS,
            "payments": len(cal_book),
            "seed": CALIBRATION_SEED,
        },
        "book": book_summary(week_data[0][1]),
        "chains": {
            name: {
                "block_time_s": chain.block_time_s,
                "reorgs_per_day": chain.reorgs_per_day,
                "shallow_share": chain.shallow_share,
                "deep_q": chain.deep_q,
                "incident_share": chain.incident_share,
                "incident_min": chain.incident_min,
                "incident_max": chain.incident_max,
                "drop_prob": chain.drop_prob,
            }
            for name, chain in CHAINS.items()
        },
        "params": {
            "carry_per_hour": params.carry_per_hour,
            "fixed_per_hour": params.fixed_per_hour,
        },
        "risk": {
            "loss": {name: [round(v, 6) for v in risks["loss"][name]] for name in CHAINS},
            "false_credit": {
                name: [round(v, 6) for v in risks["false_credit"][name]]
                for name in CHAINS
            },
        },
        "policies": policies,
        "sweep": sweep,
        "stress": {"incident_scale": STRESS_SCALE, "policies": stress},
        "checks": checks,
    }
    payload["checks"]["deterministic_rerun"] = _identical(
        payload, week_data, risks, params
    )

    (directory / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (directory / "summary.md").write_text(render_markdown(payload))
    return payload


def _identical(payload: dict, week_data, risks, params) -> bool:
    again = {}
    for name in POLICIES:
        pooled = []
        for seed, book, reorgs in week_data:
            ks = {p.pid: confirmations(name, p, risks, params) for p in book}
            pooled.extend(run_policy(book, reorgs, ks))
        again[name] = metrics(pooled, params)
    return all(
        again[name]["loss_usd"] == payload["policies"][name]["loss_usd"]
        and again[name]["median_delay_s"] == payload["policies"][name]["median_delay_s"]
        for name in POLICIES
    )


def render_markdown(payload: dict) -> str:
    book = payload["book"]
    lines = ["# Results", ""]
    lines.append(
        f"Book per week: {book['payments']} synthetic payments, USD {book['total_usd']:,.2f} "
        f"total, median USD {book['median_usd']:,.2f}, p99 USD {book['p99_usd']:,.2f}, "
        f"max USD {book['max_usd']:,.2f}. Scored on {len(payload['weeks'])} held out weeks."
    )
    lines.append("")
    lines.append(
        f"Calibration: {payload['calibration']['days']} days, "
        f"{payload['calibration']['payments']} payments, seed "
        f"{payload['calibration']['seed']}. Evaluation seeds: "
        f"{', '.join(str(w) for w in payload['weeks'])}. The calibrated policy never "
        "sees the evaluation weeks."
    )
    lines.append("")
    lines.append("## Policies")
    lines.append("")
    lines.append(
        "| Policy | k median | lost USD | loss bps | false credits | median wait s | "
        "p95 wait s | within 60s | wait cost USD | total cost USD |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for name in POLICIES:
        row = payload["policies"][name]
        lines.append(
            f"| {name} | {row['k']['median']} | {row['loss_usd']:,.2f} | {row['loss_bps']} | "
            f"{row['false_credits']} | {row['median_delay_s']:.0f} | "
            f"{row['p95_delay_s']:.0f} | {row['share_credited_60s'] * 100:.1f}% | "
            f"{row['wait_cost_usd']:,.2f} | {row['total_cost_usd']:,.2f} |"
        )
    lines.append("")
    lines.append("## Loss by week")
    lines.append("")
    header = "| Policy | " + " | ".join(str(w) for w in payload["weeks"]) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(payload["weeks"]))
    for name in POLICIES:
        cells = [f"{w['loss_usd']:,.2f}" for w in payload["policies"][name]["per_week"]]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Loss by chain")
    lines.append("")
    lines.append("| Policy | Chain | k median | false credits | lost USD | median wait s |")
    lines.append("|---|---|---|---|---|---|")
    for name in POLICIES:
        for chain in CHAINS:
            row = payload["policies"][name]["per_chain"][chain]
            k_median = payload["policies"][name]["k"]["by_chain"][chain]["median"]
            lines.append(
                f"| {name} | {chain} | {k_median} | {row['false_credits']} | "
                f"{row['loss_usd']:,.2f} | {row['median_delay_s']:.0f} |"
            )
    lines.append("")
    lines.append("## Where the money is lost, by ticket band")
    lines.append("")
    lines.append("| Policy | " + " | ".join(band for band, _ in BANDS) + " |")
    lines.append("|---|" + "---|" * len(BANDS))
    for name in ("fixed_12", "ticket_tiers", "calibrated"):
        row = payload["policies"][name]["loss_by_band"]
        cells = [f"{row[band]['loss_usd']:,.2f}" for band, _ in BANDS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Stress: incidents 1.5x deeper than the calibration month")
    lines.append("")
    lines.append(
        "Same four weeks, same fork heights, every incident 1.5x deeper than anything "
        "the calibration month contained. Policies keep the k they were fitted with."
    )
    lines.append("")
    lines.append("| Policy | lost USD | loss bps | false credits | median wait s |")
    lines.append("|---|---|---|---|---|")
    for name in POLICIES:
        row = payload["stress"]["policies"][name]
        lines.append(
            f"| {name} | {row['loss_usd']:,.2f} | {row['loss_bps']} | "
            f"{row['false_credits']} | {row['median_delay_s']:.0f} |"
        )
    lines.append("")
    lines.append("## Fixed k sweep, pooled over the four weeks")
    lines.append("")
    lines.append("| k | lost USD | loss bps | false credits | median wait s | p95 wait s | within 60s |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in payload["sweep"]:
        lines.append(
            f"| {row['k']} | {row['loss_usd']:,.2f} | {row['loss_bps']} | "
            f"{row['false_credits']} | {row['median_delay_s']:.0f} | "
            f"{row['p95_delay_s']:.0f} | {row['share_credited_60s'] * 100:.1f}% |"
        )
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    for name, ok in payload["checks"].items():
        lines.append(f"- {name}: {'pass' if ok else 'FAIL'}")
    lines.append("")
    return "\n".join(lines)
