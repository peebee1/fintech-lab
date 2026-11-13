"""Assemble the bench: fit, distort, recalibrate, score, price.

Everything is measured on the holdout slice. The calibration slice is only ever
seen by the two parameter Platt fit, and the training slice only by the scorecard.
"""

from __future__ import annotations

from . import book as book_mod
from . import metrics, policy
from .calibrate import apply_platt, fit_platt
from .models import Scorecard, temper

SHARPEN = 2.1
FLATTEN = 0.55


def _slice_report(preds: list[float], loans: list[book_mod.Loan]) -> dict:
    labels = [loan.defaulted for loan in loans]
    report = metrics.all_metrics(preds, labels)
    report["policy"] = policy.evaluate(preds, loans).as_dict()
    return report


def run(seed: int = 13, n: int = 6000) -> dict:
    loans = book_mod.build(seed=seed, n=n)
    parts = book_mod.split(loans)
    train, calib, holdout = parts["train"], parts["calibration"], parts["holdout"]

    card = Scorecard(l2=1.0).fit(train)
    holdout_raw = card.predict(holdout)
    calib_raw = card.predict(calib)

    base = {"scorecard": holdout_raw}
    base["overconfident"] = [temper(p, SHARPEN) for p in holdout_raw]
    base["hedged"] = [temper(p, FLATTEN) for p in holdout_raw]

    calib_variants = {
        "scorecard": calib_raw,
        "overconfident": [temper(p, SHARPEN) for p in calib_raw],
        "hedged": [temper(p, FLATTEN) for p in calib_raw],
    }

    calib_labels = [loan.defaulted for loan in calib]
    models: dict[str, dict] = {}
    for name, holdout_preds in base.items():
        a, b = fit_platt(calib_variants[name], calib_labels)
        recalibrated = apply_platt(holdout_preds, a, b)
        entry = _slice_report(holdout_preds, holdout)
        entry["platt"] = {"a": round(a, 4), "b": round(b, 4)}
        entry["recalibrated"] = _slice_report(recalibrated, holdout)
        models[name] = entry

    total_exposure = sum(loan.exposure for loan in loans)
    holdout_exposure = sum(loan.exposure for loan in holdout)
    observed_rate = sum(loan.defaulted for loan in loans) / len(loans)
    true_expected_loss = sum(loan.true_pd * loan.exposure * policy.LGD for loan in loans)

    def auc_of(name: str) -> float:
        return models[name]["auc"]

    over, over_fixed = models["overconfident"], models["overconfident"]["recalibrated"]
    base_entry = models["scorecard"]

    exposure_scale = holdout_exposure / 1_000_000.0
    gap = base_entry["policy"]["value"] - over["policy"]["value"]
    closed = over_fixed["policy"]["value"] - over["policy"]["value"]

    payload = {
        "provenance": {
            "data": book_mod.SYNTHETIC,
            "seed": seed,
            "n": n,
            "generator": "uwcal/book.py, true_pd from TRUE_COEFFICIENTS",
        },
        "book": {
            "loans": len(loans),
            "total_exposure": round(total_exposure, 2),
            "observed_default_rate": round(observed_rate, 5),
            "true_expected_loss": round(true_expected_loss, 2),
            "true_loss_rate_of_exposure": round(true_expected_loss / total_exposure, 5),
        },
        "splits": {name: len(part) for name, part in parts.items()},
        "holdout_exposure": round(holdout_exposure, 2),
        "holdout_exposure_millions": round(exposure_scale, 4),
        "coefficients": card.coefficients(),
        "settings": {"sharpen_k": SHARPEN, "flatten_k": FLATTEN,
                     "margin": policy.MARGIN, "lgd": policy.LGD,
                     "break_even_pd": round(policy.BREAK_EVEN_PD, 4)},
        "models": models,
        "headline": {
            "auc_identical": auc_of("scorecard") == auc_of("overconfident") == auc_of("hedged"),
            "auc": base_entry["auc"],
            "brier_calibrated": base_entry["brier"],
            "brier_overconfident": over["brier"],
            "brier_overconfident_recalibrated": over_fixed["brier"],
            "brier_increase_pct": round(100.0 * (over["brier"] / base_entry["brier"] - 1.0), 2),
            "brier_reduction_pct": round(100.0 * (1.0 - over_fixed["brier"] / over["brier"]), 2),
            "ece_calibrated": base_entry["ece_10"],
            "ece_overconfident": over["ece_10"],
            "ece_overconfident_recalibrated": over_fixed["ece_10"],
            "approval_rate_calibrated": base_entry["policy"]["approval_rate"],
            "approval_rate_overconfident": over["policy"]["approval_rate"],
            "approval_rate_overconfident_recalibrated": over_fixed["policy"]["approval_rate"],
            "value_calibrated": base_entry["policy"]["value"],
            "value_overconfident": over["policy"]["value"],
            "value_overconfident_recalibrated": over_fixed["policy"]["value"],
            "value_gap": round(gap, 2),
            "value_gap_closed": round(closed, 2),
            "value_gap_closed_pct": round(100.0 * closed / gap, 2) if gap else 0.0,
            "loss_multiple_overconfident": over["policy"]["loss_multiple"],
            "loss_multiple_overconfident_recalibrated": over_fixed["policy"]["loss_multiple"],
            "loss_multiple_calibrated": base_entry["policy"]["loss_multiple"],
            "slope_calibrated": models["scorecard"]["platt"]["a"],
            "slope_overconfident": over["platt"]["a"],
            "slope_hedged": models["hedged"]["platt"]["a"],
        },
    }
    return payload


def summary_text(payload: dict) -> str:
    h = payload["headline"]
    p = payload["provenance"]
    lines = [
        f"synthetic book, seed {p['seed']}, {payload['book']['loans']} loans, "
        f"{payload['book']['total_exposure']:,.0f} exposure",
        f"holdout {payload['splits']['holdout']} loans, break even PD {payload['settings']['break_even_pd']}",
        "",
        f"AUC is identical across all three models: {h['auc']:.4f}",
        "",
        "model            brier    logloss   ece10   approval   value",
    ]
    for name in ("scorecard", "overconfident", "hedged"):
        m = payload["models"][name]
        lines.append(
            f"{name:<16} {m['brier']:.4f}   {m['log_loss']:.4f}    "
            f"{m['ece_10']:.4f}  {m['policy']['approval_rate']:.4f}     {m['policy']['value']:,.0f}"
        )
    lines.append("")
    lines.append("after Platt scaling on the calibration slice")
    for name in ("scorecard", "overconfident", "hedged"):
        m = payload["models"][name]["recalibrated"]
        lines.append(
            f"{name:<16} {m['brier']:.4f}   {m['log_loss']:.4f}    "
            f"{m['ece_10']:.4f}  {m['policy']['approval_rate']:.4f}     {m['policy']['value']:,.0f}"
        )
    lines.extend(
        [
            "",
            f"overconfident brier {h['brier_overconfident']:.4f} vs calibrated {h['brier_calibrated']:.4f} "
            f"({h['brier_increase_pct']:+.1f}%)",
            f"platt cut brier by {h['brier_reduction_pct']:.1f}% and ece from "
            f"{h['ece_overconfident']:.4f} to {h['ece_overconfident_recalibrated']:.4f}",
            f"policy value gap {h['value_gap']:,.0f}, closed {h['value_gap_closed_pct']:.1f}% by recalibration",
            f"reported loss multiple before {h['loss_multiple_overconfident']:.3f}, "
            f"after {h['loss_multiple_overconfident_recalibrated']:.3f}",
        ]
    )
    return "\n".join(lines)
