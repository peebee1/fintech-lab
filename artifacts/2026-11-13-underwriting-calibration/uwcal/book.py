"""A synthetic, labeled settled loan book.

Every number in this bench is produced by this module from one seed. The data is
generated, not sampled from a lender, and the README says so. The generator exists
because an underwriting eval needs a probability that is *true* somewhere: without
a known generating process there is nothing to be calibrated against.

Features are the kind a thin file decision actually sees: debt to income, revolving
utilization, loan to value, income, recent delinquencies, employment tenure.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

SYNTHETIC = "synthetic"

FEATURES = (
    "dti",
    "utilization",
    "ltv",
    "log_income",
    "delinquencies",
    "tenure_months",
)

TRUE_COEFFICIENTS = {
    "intercept": -4.85,
    "dti": 3.55,
    "utilization": 1.25,
    "ltv": 0.85,
    "log_income": -0.85,
    "delinquencies": 0.52,
    "tenure_months": -0.0032,
}

INCOME_MEDIAN_K = 52.0


@dataclass(frozen=True)
class Loan:
    loan_id: int
    dti: float
    utilization: float
    ltv: float
    income_k: float
    delinquencies: int
    tenure_months: int
    exposure: float
    defaulted: int
    true_pd: float

    def features(self) -> list[float]:
        return [
            self.dti,
            self.utilization,
            self.ltv,
            math.log(self.income_k),
            float(self.delinquencies),
            float(self.tenure_months),
        ]


def sigmoid(z: float) -> float:
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def logit(p: float, floor: float = 1e-6) -> float:
    p = min(max(p, floor), 1.0 - floor)
    return math.log(p / (1.0 - p))


def true_pd(dti: float, utilization: float, ltv: float, income_k: float,
            delinquencies: int, tenure_months: int) -> float:
    c = TRUE_COEFFICIENTS
    z = (
        c["intercept"]
        + c["dti"] * dti
        + c["utilization"] * utilization
        + c["ltv"] * ltv
        + c["log_income"] * (math.log(income_k) - math.log(INCOME_MEDIAN_K))
        + c["delinquencies"] * delinquencies
        + c["tenure_months"] * tenure_months
    )
    return sigmoid(z)


def build(seed: int = 13, n: int = 6000) -> list[Loan]:
    """One loan book, deterministic in the seed.

    Ids are assigned after the draw and before the outcome is taken, so an id
    based tie break cannot see the label.
    """
    rng = random.Random(seed)
    drafts = []
    for _ in range(n):
        # dti: mostly 0.1 to 0.65, a thin tail into the 0.85s.
        dti = 0.04 + 0.86 * rng.betavariate(2.1, 3.0)
        utilization = min(1.35, rng.gammavariate(2.0, 0.27))
        # ltv: purchase loans clustered near 0.8, a small cash out tail.
        ltv = min(1.10, max(0.20, rng.gauss(0.78, 0.14)))
        income_k = math.exp(rng.gauss(math.log(INCOME_MEDIAN_K), 0.52))
        delinquencies = rng.choices(
            [0, 1, 2, 3, 4], weights=[74, 14, 7, 3, 2], k=1
        )[0]
        tenure_months = rng.randint(1, 180)
        exposure = round(math.exp(rng.gauss(math.log(9000.0), 0.72)), 2)
        drafts.append((dti, utilization, ltv, income_k, delinquencies,
                       tenure_months, exposure))

    # Shuffle before numbering: a model tuned by id order is a model of the queue.
    rng.shuffle(drafts)

    loans: list[Loan] = []
    for idx, (dti, utilization, ltv, income_k, delinquencies, tenure, exposure) in enumerate(drafts):
        pd_true = true_pd(dti, utilization, ltv, income_k, delinquencies, tenure)
        defaulted = 1 if rng.random() < pd_true else 0
        loans.append(
            Loan(
                loan_id=idx,
                dti=round(dti, 4),
                utilization=round(utilization, 4),
                ltv=round(ltv, 4),
                income_k=round(income_k, 2),
                delinquencies=delinquencies,
                tenure_months=tenure,
                exposure=exposure,
                defaulted=defaulted,
                true_pd=pd_true,
            )
        )
    return loans


def split(loans: list[Loan], train: int = 3000, calibration: int = 1500) -> dict[str, list[Loan]]:
    """Train, calibration, holdout. The calibration slice is never used for fitting.

    A small book falls back to proportions so tests can run a 1,200 loan version
    of the same bench without a second code path.
    """
    total = len(loans)
    if train + calibration >= total:
        train = max(1, int(total * 0.5))
        calibration = max(1, int(total * 0.25))
    if train + calibration >= total:
        raise ValueError("split leaves no holdout")
    return {
        "train": loans[:train],
        "calibration": loans[train:train + calibration],
        "holdout": loans[train + calibration:],
    }
