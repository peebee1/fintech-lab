"""Scoring for detection and for triage under a fixed review budget."""

from __future__ import annotations

import random

from .model import BREAK_CLASSES, Break


def score(truth: list[dict], breaks: list[Break]) -> dict:
    truth_keys = {(row["class"], row["key"]) for row in truth}
    found_keys = {(brk.cls, brk.key) for brk in breaks}
    correct = truth_keys & found_keys
    precision = len(correct) / len(found_keys) if found_keys else 0.0
    recall = len(correct) / len(truth_keys) if truth_keys else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    per_class = []
    for cls in BREAK_CLASSES:
        expected = {key for (c, key) in truth_keys if c == cls}
        emitted = {key for (c, key) in found_keys if c == cls}
        hit = expected & emitted
        per_class.append(
            {
                "class": cls,
                "truth": len(expected),
                "detected": len(emitted),
                "correct": len(hit),
                "precision": round(len(hit) / len(emitted), 4) if emitted else 0.0,
                "recall": round(len(hit) / len(expected), 4) if expected else 0.0,
            }
        )

    return {
        "truth": len(truth_keys),
        "detected": len(found_keys),
        "correct": len(correct),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "per_class": per_class,
    }


def triage(breaks: list[Break], budget: int, rng: random.Random | None = None) -> dict:
    """Share of rupee exposure a reviewer sees in the first `budget` tickets."""
    rng = rng or random.Random(23)
    total = sum(brk.impact for brk in breaks)
    if not breaks or total == 0:
        return {
            "budget": budget,
            "breaks": len(breaks),
            "impact_paise": 0,
            "coverage_by_impact": 0.0,
            "coverage_by_arrival": 0.0,
            "coverage_random": 0.0,
            "top_ten_share": 0.0,
        }

    ranked = sorted(breaks, key=lambda brk: (-brk.impact, brk.cls, brk.key))
    covered = sum(brk.impact for brk in ranked[:budget])

    arrival = sum(brk.impact for brk in breaks[:budget])

    trials = 50
    random_covered = 0.0
    for _ in range(trials):
        sample = rng.sample(breaks, min(budget, len(breaks)))
        random_covered += sum(brk.impact for brk in sample)
    random_covered /= trials

    return {
        "budget": budget,
        "breaks": len(breaks),
        "impact_paise": total,
        "coverage_by_impact": round(covered / total, 4),
        "coverage_by_arrival": round(arrival / total, 4),
        "coverage_random": round(random_covered / total, 4),
        "top_ten_share": round(sum(brk.impact for brk in ranked[:10]) / total, 4),
    }
