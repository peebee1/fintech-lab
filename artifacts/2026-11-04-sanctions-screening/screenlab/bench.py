"""Measure the three policies at a fixed analyst review budget.

The constraint that matters in screening is not a similarity threshold, it is
how many cases an analyst can clear per day. So every policy is scored at the
same budget: rank all alerts, review the top K distinct customers, count what
was true. A policy that cannot order its own alerts wastes that budget on ties.
"""

from __future__ import annotations

from . import match
from .data import build, digest
from .model import Alert, Dataset

REVIEW_BUDGET = 48          # 2 percent of the book, one analyst day
SWEEP = (24, 48, 96, 192)   # 1, 2, 4 and 8 percent of the book


def order(alerts: list[Alert], reverse_id: bool = False) -> list[Alert]:
    """Best alert per customer, highest score first, subject id to break ties."""
    best: dict[str, Alert] = {}
    for alert in alerts:
        current = best.get(alert.subject_id)
        if current is None or (alert.score, alert.entry_id) > (current.score, current.entry_id):
            best[alert.subject_id] = alert
    by_id = sorted(best.values(), key=lambda a: a.subject_id, reverse=reverse_id)
    return sorted(by_id, key=lambda a: -a.score)


def tie_sensitivity(dataset: Dataset, alerts: list[Alert], budget: int) -> dict:
    """How much of the result is decided by the tie break rather than the model."""
    truth = {s.subject_id: s for s in dataset.subjects}
    out = {}
    for label, reverse_id in (("ascending_id", False), ("descending_id", True)):
        reviewed = order(alerts, reverse_id)[:budget]
        out[label] = sum(1 for a in reviewed if truth[a.subject_id].truth_entry_id)
    return out


def evaluate(dataset: Dataset, alerts: list[Alert], budget: int) -> dict:
    truth = {s.subject_id: s for s in dataset.subjects}
    ordered = order(alerts)
    reviewed = ordered[:budget]
    designated = [s for s in dataset.subjects if s.truth_entry_id]
    hits = [a for a in reviewed if truth[a.subject_id].truth_entry_id]
    namesakes = [a for a in reviewed if truth[a.subject_id].truth_kind == "namesake"]
    precision = len(hits) / len(reviewed) if reviewed else 0.0
    recall = len(hits) / len(designated) if designated else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    # A true match that was alerted but never reached inside the budget is a
    # ranking loss, not a coverage loss. The two need separate numbers.
    alerted = {a.subject_id for a in ordered if truth[a.subject_id].truth_entry_id}
    top_score = ordered[0].score if ordered else 0.0
    at_top = sum(1 for a in ordered if a.score == top_score)
    return {
        "alert_pairs": len(alerts),
        "queued_customers": len(ordered),
        "reviewed": len(reviewed),
        "true_hits": len(hits),
        "namesake_reviews": len(namesakes),
        "designated_alerted": len(alerted),
        "ranking_loss": len(alerted) - len(hits),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "missed": len(designated) - len(hits),
        "top_score": top_score,
        "customers_at_top_score": at_top,
        "queue_days": round(len(ordered) / budget, 2) if budget else None,
        "frozen_customers_per_catch": (
            round(len(namesakes) / len(hits), 2) if hits else None),
    }


def by_kind(dataset: Dataset, alerts: list[Alert], budget: int) -> dict:
    truth = {s.subject_id: s for s in dataset.subjects}
    reviewed = order(alerts)[:budget]
    caught = {truth[a.subject_id].subject_id for a in reviewed if truth[a.subject_id].truth_entry_id}
    out: dict[str, dict] = {}
    for kind in ("exact", "alias", "year_only", "relocated", "thin_kyc", "kunya"):
        population = [s for s in dataset.subjects if s.truth_kind == kind]
        hit = sum(1 for s in population if s.subject_id in caught)
        out[kind] = {
            "population": len(population),
            "caught": hit,
            "recall": round(hit / len(population), 4) if population else 0.0,
        }
    return out


def rules(alerts: list[Alert], dataset: Dataset) -> dict:
    truth = {s.subject_id: s for s in dataset.subjects}
    out: dict[str, dict] = {}
    for alert in alerts:
        bucket = out.setdefault(alert.rule, {"alerts": 0, "true": 0})
        bucket["alerts"] += 1
        if truth[alert.subject_id].truth_entry_id:
            bucket["true"] += 1
    for bucket in out.values():
        bucket["precision"] = round(bucket["true"] / bucket["alerts"], 4) if bucket["alerts"] else 0.0
    return dict(sorted(out.items()))


def run(dataset: Dataset | None = None, budget: int = REVIEW_BUDGET,
        sweep: tuple[int, ...] = SWEEP) -> dict:
    dataset = build() if dataset is None else dataset
    stats: dict[str, dict] = {name: {} for name in match.POLICIES}
    alerts_by_policy = {name: match.run(dataset, name, stats[name]) for name in match.POLICIES}
    designated = [s for s in dataset.subjects if s.truth_entry_id]

    policies = {
        name: evaluate(dataset, alerts, budget) for name, alerts in alerts_by_policy.items()
    }
    headline_policy = "entity_resolution"
    headline = policies[headline_policy]

    return {
        "meta": {
            "seed": dataset.seed,
            "dataset_sha256": digest(dataset),
            "listed_entries": len(dataset.entries),
            "book_size": len(dataset.subjects),
            "true_matches": len(designated),
            "namesakes": sum(1 for s in dataset.subjects if s.truth_kind == "namesake"),
            "review_budget": budget,
            "review_budget_share": round(budget / len(dataset.subjects), 4),
            "synthetic": True,
            "command": "PYTHONPATH=artifacts/2026-11-04-sanctions-screening "
                       "uv run python -m screenlab.cli screen",
        },
        "policies": policies,
        "by_kind": {name: by_kind(dataset, alerts, budget)
                    for name, alerts in alerts_by_policy.items()},
        "budget_sweep": {
            name: [{"budget": b, **evaluate(dataset, alerts, b)} for b in sweep]
            for name, alerts in alerts_by_policy.items()
        },
        "rules": rules(alerts_by_policy[headline_policy], dataset),
        "suppressed": stats[headline_policy],
        "tie_break": {
            name: tie_sensitivity(dataset, alerts, budget)
            for name, alerts in alerts_by_policy.items()
        },
        "headline": (
            f"at {budget} reviews, entity resolution catches {headline['true_hits']} of "
            f"{len(designated)} designated customers and name-only catches "
            f"{policies['name_only']['true_hits']}"
        ),
    }


def summary_text(payload: dict) -> str:
    meta = payload["meta"]
    lines = [
        f"book {meta['book_size']} customers, list {meta['listed_entries']} entries, "
        f"{meta['true_matches']} true matches, {meta['namesakes']} namesakes",
        f"review budget {meta['review_budget']} cases "
        f"({meta['review_budget_share']:.2%} of the book)",
        "",
        f"{'policy':<18}{'reviewed':>9}{'caught':>8}{'namesakes':>11}"
        f"{'precision':>11}{'recall':>8}{'f1':>7}{'days':>7}",
    ]
    for name, row in payload["policies"].items():
        lines.append(
            f"{name:<18}{row['reviewed']:>9}{row['true_hits']:>8}"
            f"{row['namesake_reviews']:>11}{row['precision']:>11.3f}"
            f"{row['recall']:>8.3f}{row['f1']:>7.3f}{row['queue_days']:>7.1f}"
        )
    lines.append("")
    lines.append("queue and ordering at the same budget")
    lines.append(f"{'policy':<18}{'queued':>8}{'days':>7}{'top':>7}{'at top':>9}"
                 f"{'alerted true':>14}{'ranking loss':>14}")
    for name, row in payload["policies"].items():
        lines.append(
            f"{name:<18}{row['queued_customers']:>8}{row['queue_days']:>7.1f}"
            f"{row['top_score']:>7.2f}{row['customers_at_top_score']:>9}"
            f"{row['designated_alerted']:>14}{row['ranking_loss']:>14}"
        )
    lines.append("")
    lines.append("recall by class of true match, entity resolution versus name only")
    kinds = payload["by_kind"]["entity_resolution"]
    lines.append(f"{'class':<14}{'n':>4}{'er':>6}{'name only':>12}")
    for kind, row in kinds.items():
        other = payload["by_kind"]["name_only"][kind]
        lines.append(f"{kind:<14}{row['population']:>4}{row['caught']:>6}{other['caught']:>12}")
    lines.append("")
    lines.append("tie break sensitivity: true catches with customer id ascending vs descending")
    for name, row in payload["tie_break"].items():
        lines.append(f"  {name:<24}{row['ascending_id']:>4} vs {row['descending_id']:>4}")
    lines.append("")
    lines.append("entity resolution alerts by rule")
    for rule, row in payload["rules"].items():
        lines.append(f"  {rule:<26}{row['alerts']:>5} alerts{row['true']:>5} true"
                     f"  precision {row['precision']:.3f}")
    for reason, count in payload.get("suppressed", {}).items():
        lines.append(f"  suppressed {reason}: {count} pairs")
    return "\n".join(lines)
