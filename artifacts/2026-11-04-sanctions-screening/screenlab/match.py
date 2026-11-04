"""Three screening policies, each returning ranked alerts with a named rule.

The point of the artifact is the comparison, so every policy emits the same
Alert shape and the bench treats them identically. Only the evidence differs.
"""

from __future__ import annotations

from .model import Alert, Dataset, ListEntry, Subject
from .text import fold, jaro_winkler, similarity

POLICIES = ("exact_name", "name_only", "name_country", "entity_resolution")

NAME_ONLY_THRESHOLD = 0.85
ALERT_THRESHOLD = 0.88
# A date of birth conflict is positive evidence against a match, but only a
# near exact name is allowed to outrank it. Below this, the conflict suppresses
# the alert instead of queueing it.
CONFLICT_SUPPRESS_BELOW = 0.95


def dob_state(entry: ListEntry, subject: Subject) -> str:
    """exact, year, absent, or conflict. Absent is not the same as conflict."""
    if not entry.dob:
        return "absent"
    if not subject.dob:
        return "absent"
    if len(entry.dob) == 4:
        return "year" if subject.dob.split("-")[0] == entry.dob else "conflict"
    return "exact" if subject.dob == entry.dob else "conflict"


def country_state(entry: ListEntry, subject: Subject) -> str:
    return "match" if subject.country in entry.countries else "conflict"


def id_state(entry: ListEntry, subject: Subject) -> str:
    return "exact" if subject.national_id in entry.id_numbers else "absent"


def score_pair(subject: Subject, entry: ListEntry) -> tuple[float, float, ListEntry]:
    """Return (best full-name Jaro-Winkler, best of three views) for one pair."""
    folded = fold(subject.name)
    best_jw = 0.0
    best_view = 0.0
    for listed in entry.all_names():
        best_jw = max(best_jw, jaro_winkler(folded, fold(listed)))
        best_view = max(best_view, similarity(subject.name, listed))
    return best_jw, best_view, entry


def _entity_score(subject: Subject, entry: ListEntry, name_score: float
                  ) -> tuple[Alert | None, str]:
    """Return (alert, suppression reason). An empty reason means no suppression."""
    dob = dob_state(entry, subject)
    country = country_state(entry, subject)
    ident = id_state(entry, subject)
    if name_score < ALERT_THRESHOLD and ident != "exact":
        return None, ""
    if dob == "conflict" and ident != "exact" and name_score < CONFLICT_SUPPRESS_BELOW:
        return None, "weak_name_dob_conflict"

    score = name_score
    reasons: list[str] = []
    if dob == "exact":
        score += 0.20
        reasons.append("date of birth exact")
    elif dob == "year":
        score += 0.12
        reasons.append("date of birth year matches")
    elif dob == "absent":
        score -= 0.04
        reasons.append("date of birth missing on one side")
    else:
        score -= 0.32
        reasons.append("date of birth conflicts")
    if country == "match":
        score += 0.07
        reasons.append("country matches")
    else:
        score -= 0.06
        reasons.append("country conflicts")
    if ident == "exact":
        score = 1.0
        reasons.append("identity number in list")

    if ident == "exact":
        rule = "id_exact"
    elif dob == "conflict":
        rule = "name_over_dob_conflict"
    elif name_score >= 0.97 and dob in {"exact", "year"}:
        rule = "name_exact_dob"
    elif name_score >= 0.90 and dob in {"exact", "year"}:
        rule = "name_close_dob"
    elif name_score >= ALERT_THRESHOLD and dob in {"exact", "year"}:
        rule = "name_variant_dob"
    elif name_score >= 0.90 and dob == "absent":
        rule = "name_no_dob"
    else:
        rule = "name_only"

    return Alert(
        subject_id=subject.subject_id,
        entry_id=entry.entry_id,
        name_score=round(name_score, 4),
        score=round(max(0.0, min(1.0, score)), 4),
        rule=rule,
        reasons=tuple(reasons),
    ), ""


def run(dataset: Dataset, policy: str, stats: dict | None = None) -> list[Alert]:
    """Screen every subject against every list entry under one policy.

    `stats`, when given, collects suppression counters so the bench can report
    what a rule removed rather than only what it kept.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    alerts: list[Alert] = []
    for subject in dataset.subjects:
        folded = fold(subject.name)
        for entry in dataset.entries:
            if policy == "exact_name":
                if any(folded == fold(name) for name in entry.all_names()):
                    alerts.append(Alert(
                        subject_id=subject.subject_id, entry_id=entry.entry_id,
                        name_score=1.0, score=1.0, rule="exact_name",
                        reasons=("name identical after folding",)))
                continue
            best_jw, best_view, _ = score_pair(subject, entry)
            if policy == "name_only":
                if best_jw >= NAME_ONLY_THRESHOLD:
                    alerts.append(Alert(
                        subject_id=subject.subject_id, entry_id=entry.entry_id,
                        name_score=round(best_jw, 4), score=round(best_jw, 4),
                        rule="name_only",
                        reasons=("name similarity only",)))
            elif policy == "name_country":
                if best_jw >= NAME_ONLY_THRESHOLD and country_state(entry, subject) == "match":
                    alerts.append(Alert(
                        subject_id=subject.subject_id, entry_id=entry.entry_id,
                        name_score=round(best_jw, 4), score=round(best_jw, 4),
                        rule="name_and_country",
                        reasons=("name similarity", "country matches")))
            else:
                alert, reason = _entity_score(subject, entry, best_view)
                if alert is not None:
                    alerts.append(alert)
                elif reason and stats is not None:
                    stats[reason] = stats.get(reason, 0) + 1
    return alerts
