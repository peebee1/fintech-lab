"""Measurement: numbers, markdown, and the reconciliation check.

Every figure the README quotes is printed here. The reconciliation runs on every
eval so a broken total fails loudly instead of looking like a good quarter.

Currency discipline: the book holds EUR on card and SEPA and INR on UPI. Amounts
are never added across currencies, because a rate built on that sum would be an
FX assumption in disguise. Cross rail rates are the equal weight mean of the
three rail rates, and the header says so.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from . import rails
from .model import (
    CLEAN,
    COLLECTED_STATES,
    DECLINED,
    EXPOSED,
    NOT_PRESENTED,
    REVERSED,
    Population,
    RunResult,
    STATES,
)
from .money import bps, format_minor
from .sim import PLANNERS, run


def _sum_state(rows, state: str) -> int:
    return sum(r.amount_minor for r in rows if r.state == state)


@dataclass(frozen=True)
class RailMetrics:
    rail: str
    currency: str
    invoices: int
    billed_minor: int
    clean_minor: int
    exposed_minor: int
    reversed_minor: int
    declined_minor: int
    not_presented_minor: int
    on_time: int
    over_cap_invoices: int
    over_cap_minor: int
    latency_mean: float | None

    @property
    def kept_minor(self) -> int:
        return self.clean_minor + self.exposed_minor

    def rate(self, amount: int) -> int:
        return bps(amount, self.billed_minor)

    @property
    def kept_bps(self) -> int:
        return self.rate(self.kept_minor)

    @property
    def exposure_bps(self) -> int:
        return self.rate(self.exposed_minor)

    @property
    def reversed_bps(self) -> int:
        return self.rate(self.reversed_minor)

    @property
    def declined_bps(self) -> int:
        return self.rate(self.declined_minor)

    @property
    def not_presented_bps(self) -> int:
        return self.rate(self.not_presented_minor)

    @property
    def risk_adjusted_bps(self) -> int:
        return self.rate(self.clean_minor)

    @property
    def on_time_bps(self) -> int:
        return bps(self.on_time, self.invoices)

    @property
    def over_cap_bps(self) -> int:
        return bps(self.over_cap_minor, self.billed_minor)


@dataclass(frozen=True)
class Metrics:
    planner: str
    label: str
    invoices: int
    billed_minor: int
    clean_minor: int
    exposed_minor: int
    reversed_minor: int
    declined_minor: int
    not_presented_minor: int
    presentations: int
    settled_presentations: int
    reversible_presentations: int
    latency_median: int | None
    latency_p90: int | None
    latency_mean: float | None
    on_time: int
    per_rail: dict[str, RailMetrics] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)
    by_state: dict[str, int] = field(default_factory=dict)

    @property
    def kept_minor(self) -> int:
        return self.clean_minor + self.exposed_minor

    @property
    def landed_minor(self) -> int:
        return self.kept_minor + self.reversed_minor

    @property
    def risk_adjusted_minor(self) -> int:
        """What the book is worth if every refund right still outstanding is exercised."""
        return self.clean_minor

    def mean(self, name: str) -> int:
        """Equal weight mean of a per rail rate. No currency is added to another."""
        rates = [getattr(rail, f"{name}_bps") for rail in self.per_rail.values()]
        return round(sum(rates) / len(rates)) if rates else 0

    @property
    def on_time_bps(self) -> int:
        return bps(self.on_time, self.invoices)


def percentile(values: list[int], p: int) -> int | None:
    """Nearest rank percentile. Deterministic, no interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, round(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarise(result: RunResult, population: Population) -> Metrics:
    outcomes: dict[str, int] = {}
    for attempt in result.attempts:
        outcomes[attempt.outcome] = outcomes.get(attempt.outcome, 0) + 1

    states: dict[str, int] = {state: 0 for state in STATES}
    latency: list[int] = []
    on_time = 0
    for resolution in result.resolutions:
        states[resolution.state] = states.get(resolution.state, 0) + 1
        if resolution.state in COLLECTED_STATES and resolution.days_late is not None:
            latency.append(resolution.days_late)
            if resolution.days_late <= 0:
                on_time += 1

    per_rail: dict[str, RailMetrics] = {}
    for rail_id, spec in rails.RAILS.items():
        rows = [r for r in result.resolutions if r.rail == rail_id]
        if not rows:
            continue
        over_cap = [r for r in rows if spec.needs_afa(r.amount_minor)]
        rail_latency = [
            r.days_late
            for r in rows
            if r.state in COLLECTED_STATES and r.days_late is not None
        ]
        per_rail[rail_id] = RailMetrics(
            rail=rail_id,
            currency=spec.currency,
            invoices=len(rows),
            billed_minor=sum(r.amount_minor for r in rows),
            clean_minor=_sum_state(rows, CLEAN),
            exposed_minor=_sum_state(rows, EXPOSED),
            reversed_minor=_sum_state(rows, REVERSED),
            declined_minor=_sum_state(rows, DECLINED),
            not_presented_minor=_sum_state(rows, NOT_PRESENTED),
            on_time=sum(
                1 for r in rows if r.state in COLLECTED_STATES and (r.days_late or 0) <= 0
            ),
            over_cap_invoices=len(over_cap),
            over_cap_minor=sum(r.amount_minor for r in over_cap),
            latency_mean=(
                round(sum(rail_latency) / len(rail_latency), 1) if rail_latency else None
            ),
        )

    return Metrics(
        planner=result.planner,
        label=PLANNERS[result.planner].label,
        invoices=len(result.resolutions),
        billed_minor=sum(r.amount_minor for r in result.resolutions),
        clean_minor=_sum_state(result.resolutions, CLEAN),
        exposed_minor=_sum_state(result.resolutions, EXPOSED),
        reversed_minor=_sum_state(result.resolutions, REVERSED),
        declined_minor=_sum_state(result.resolutions, DECLINED),
        not_presented_minor=_sum_state(result.resolutions, NOT_PRESENTED),
        presentations=len(result.attempts),
        settled_presentations=sum(1 for a in result.attempts if a.settled),
        reversible_presentations=sum(1 for a in result.attempts if a.reversible),
        latency_median=percentile(latency, 50),
        latency_p90=percentile(latency, 90),
        latency_mean=round(sum(latency) / len(latency), 1) if latency else None,
        on_time=on_time,
        per_rail=per_rail,
        by_outcome=outcomes,
        by_state=states,
    )


def reconcile(metrics: Metrics) -> tuple[bool, list[str]]:
    """The books have to balance, and the attempt level totals have to agree.

    Two independent routes to the same number: invoice resolutions on one side,
    presentation outcomes on the other. A sign error survives one of them and
    fails the other, which is the point.
    """
    notes: list[str] = []
    ok = True

    buckets = (
        metrics.clean_minor
        + metrics.exposed_minor
        + metrics.reversed_minor
        + metrics.declined_minor
        + metrics.not_presented_minor
    )
    if buckets != metrics.billed_minor:
        ok = False
        notes.append(f"buckets {buckets} do not sum to billed {metrics.billed_minor}")

    if sum(metrics.by_state.values()) != metrics.invoices:
        ok = False
        notes.append(f"{sum(metrics.by_state.values())} states for {metrics.invoices} invoices")

    settled_states = (
        metrics.by_state.get(CLEAN, 0)
        + metrics.by_state.get(EXPOSED, 0)
        + metrics.by_state.get(REVERSED, 0)
    )
    if settled_states != metrics.settled_presentations:
        ok = False
        notes.append(
            f"{settled_states} settled invoices against {metrics.settled_presentations} presentations"
        )

    declined_presentations = sum(
        count for outcome, count in metrics.by_outcome.items() if outcome.startswith("declined")
    )
    if metrics.presentations != metrics.settled_presentations + declined_presentations:
        ok = False
        notes.append("presentations do not split into settled and declined")

    if metrics.landed_minor != metrics.kept_minor + metrics.reversed_minor:
        ok = False
        notes.append("landed does not equal kept plus reversed")

    if sum(r.billed_minor for r in metrics.per_rail.values()) != metrics.billed_minor:
        ok = False
        notes.append("rail billed does not match the total")

    if sum(r.kept_minor for r in metrics.per_rail.values()) != metrics.kept_minor:
        ok = False
        notes.append("rail kept does not match the total")

    return ok, notes


def lag_sensitivity(
    population: Population,
    lags: tuple[int, ...] = (0, 1, 2, 3, 7),
) -> list[dict]:
    """Hold the book and the planner fixed, vary only how long a revocation takes to bite.

    The revocation blind planner is the useful probe: it presents through the lag
    window on purpose, so what comes back is attributable to the lag alone.
    """
    rows: list[dict] = []
    for lag in lags:
        specs = {
            rail_id: replace(spec, revoke_lag_days=lag)
            for rail_id, spec in rails.RAILS.items()
        }
        metrics = summarise(run(population, PLANNERS["notice_aware"], specs), population)
        rows.append(
            {
                "lag_days": lag,
                "kept_bps": metrics.mean("kept"),
                "exposure_bps": metrics.mean("exposure"),
                "reversed_bps": metrics.mean("reversed"),
            }
        )
    return rows


def _table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def to_markdown(
    all_metrics: list[Metrics],
    population: Population,
    sensitivity: list[dict] | None = None,
) -> str:
    checks = [
        f"- {m.planner}: {'PASS' if ok else 'FAIL'}" + (" " + "; ".join(notes) if notes else "")
        for m, (ok, notes) in ((m, reconcile(m)) for m in all_metrics)
    ]

    collection = _table(
        ["Planner", "Mean kept", "Mean exposure", "Mean reversed", "Mean declined",
         "Mean not presented", "Mean risk adjusted", "Median days late", "p90"],
        [
            [m.planner, m.mean("kept"), m.mean("exposure"), m.mean("reversed"),
             m.mean("declined"), m.mean("not_presented"), m.mean("risk_adjusted"),
             m.latency_median, m.latency_p90]
            for m in all_metrics
        ],
    )
    per_rail = _table(
        ["Planner", "Rail", "Invoices", "Billed", "Kept", "Exposed", "Reversed",
         "Kept bps", "Exposure bps", "Risk adjusted bps"],
        [
            [m.planner, rail_id, r.invoices,
             format_minor(r.billed_minor, r.currency),
             format_minor(r.kept_minor, r.currency),
             format_minor(r.exposed_minor, r.currency),
             format_minor(r.reversed_minor, r.currency),
             r.kept_bps, r.exposure_bps, r.risk_adjusted_bps]
            for m in all_metrics
            for rail_id, r in ((rail_id, m.per_rail[rail_id]) for rail_id in ("card", "sepa", "upi")
                               if rail_id in m.per_rail)
        ],
    )
    compliant = all_metrics[-1]
    book = _table(
        ["Rail", "Invoices", "Billed", "Over cap invoices", "Over cap value share",
         "Mean days late", "On time"],
        [
            [rail_id, r.invoices, format_minor(r.billed_minor, r.currency),
             r.over_cap_invoices, f"{r.over_cap_bps} bps", r.latency_mean, f"{r.on_time_bps} bps"]
            for rail_id, r in ((rail_id, compliant.per_rail[rail_id]) for rail_id in ("card", "sepa", "upi")
                               if rail_id in compliant.per_rail)
        ],
    )
    states = _table(
        ["Planner", "Invoices", "Clean", "Exposed", "Reversed", "Declined", "Not presented"],
        [
            [m.planner, m.invoices, m.by_state.get(CLEAN, 0), m.by_state.get(EXPOSED, 0),
             m.by_state.get(REVERSED, 0), m.by_state.get(DECLINED, 0),
             m.by_state.get(NOT_PRESENTED, 0)]
            for m in all_metrics
        ],
    )
    codes = ("settled", "declined_funds", "declined_afa", "declined_revoked", "declined_too_soon")
    outcomes = _table(
        ["Planner", *codes],
        [[m.planner, *[m.by_outcome.get(code, 0) for code in codes]] for m in all_metrics],
    )

    lines = [
        "# Mandate simulator eval",
        "",
        "Produced by `mandate.cli eval`. Synthetic book, no real customers.",
        "",
        f"- subscribers: {len(population.subscribers)}",
        f"- invoices: {len(population.invoices)}",
        f"- horizon: {population.horizon_days} days",
        f"- seed: {population.seed}",
        "",
        "Per rail rates are basis points of that rail's billed amount. The mean columns are the equal",
        "weight mean of the three rail rates, because EUR and INR are never summed here.",
        "",
        "Kept is money still in the account. Exposure is money in the account that the payer still has",
        "a right to take back. Reversed is a right that was exercised. Risk adjusted is kept with every",
        "outstanding right treated as already exercised, which is the floor.",
        "",
        "## Collection",
        "",
        collection,
        "",
        "## By rail",
        "",
        per_rail,
        "",
        "## Book composition",
        "",
        book,
        "",
        "## Invoice states",
        "",
        states,
        "",
        "## Presentation outcomes",
        "",
        outcomes,
        "",
        "## Reconciliation",
        "",
        "Billed splits exactly once into the five states, and presentations split into settled and declined.",
        "",
        "\n".join(checks),
        "",
    ]
    if sensitivity:
        lines += [
            "## Revocation lag sensitivity",
            "",
            "Same book, same planner (notice and cap aware, revocation blind), only the lag changes.",
            "The lag is the window where the payer has asked to stop and the rail has not stopped yet.",
            "",
            _table(
                ["Revocation lag (days)", "Mean kept bps", "Mean exposure bps", "Mean reversed bps"],
                [[row["lag_days"], row["kept_bps"], row["exposure_bps"], row["reversed_bps"]]
                 for row in sensitivity],
            ),
            "",
        ]
    return "\n".join(lines)


def _rail_block(r: RailMetrics) -> dict:
    data = asdict(r)
    data.update(
        kept_minor=r.kept_minor,
        kept_bps=r.kept_bps,
        exposure_bps=r.exposure_bps,
        reversed_bps=r.reversed_bps,
        declined_bps=r.declined_bps,
        not_presented_bps=r.not_presented_bps,
        risk_adjusted_bps=r.risk_adjusted_bps,
        on_time_bps=r.on_time_bps,
        over_cap_bps=r.over_cap_bps,
    )
    return data


def _planner_block(m: Metrics) -> dict:
    block = asdict(m)
    block.update(
        on_time_bps=m.on_time_bps,
        mean_rates_bps={
            name: m.mean(name)
            for name in ("kept", "exposure", "reversed", "declined", "not_presented", "risk_adjusted")
        },
        per_rail={rail_id: _rail_block(r) for rail_id, r in m.per_rail.items()},
    )
    return block


def to_payload(
    all_metrics: list[Metrics],
    population: Population,
    sensitivity: list[dict] | None = None,
) -> dict:
    return {
        "population": {
            "subscribers": len(population.subscribers),
            "invoices": len(population.invoices),
            "horizon_days": population.horizon_days,
            "seed": population.seed,
        },
        "rails": {rail_id: asdict(spec) for rail_id, spec in rails.RAILS.items()},
        "sensitivity": sensitivity or [],
        "planners": [_planner_block(m) for m in all_metrics],
    }
