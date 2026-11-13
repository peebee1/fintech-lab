"""What a probability is for: approving, pricing, and reserving.

The cutoff is not a number someone liked. Net revenue on a performing loan is a
fixed share of exposure, a default costs a fixed loss given default, so the
break-even probability is margin divided by LGD. Above that line an approval is
expected to lose money.
"""

from __future__ import annotations

from dataclasses import dataclass

from .book import Loan

# Net interest and fees after funding and servicing, as a share of exposure.
MARGIN = 0.062
# Loss given default, as a share of exposure.
LGD = 0.65
# Break-even default probability for one loan.
BREAK_EVEN_PD = MARGIN / LGD


@dataclass(frozen=True)
class PolicyResult:
    cutoff: float
    approved: int
    approval_rate: float
    approved_exposure: float
    defaults_approved: int
    realized_default_rate: float
    reported_expected_loss: float
    realized_loss: float
    loss_multiple: float
    value: float
    rejected_good_count: int
    rejected_good_exposure: float
    forgone_contribution: float
    avoided_loss: float

    def as_dict(self) -> dict:
        return {
            "cutoff": round(self.cutoff, 4),
            "approved": self.approved,
            "approval_rate": round(self.approval_rate, 4),
            "approved_exposure": round(self.approved_exposure, 2),
            "defaults_approved": self.defaults_approved,
            "realized_default_rate": round(self.realized_default_rate, 4),
            "reported_expected_loss": round(self.reported_expected_loss, 2),
            "realized_loss": round(self.realized_loss, 2),
            "loss_multiple": round(self.loss_multiple, 4),
            "value": round(self.value, 2),
            "rejected_good_count": self.rejected_good_count,
            "rejected_good_exposure": round(self.rejected_good_exposure, 2),
            "forgone_contribution": round(self.forgone_contribution, 2),
            "avoided_loss": round(self.avoided_loss, 2),
        }


def evaluate(preds: list[float], loans: list[Loan], cutoff: float = BREAK_EVEN_PD,
             margin: float = MARGIN, lgd: float = LGD) -> PolicyResult:
    if len(preds) != len(loans):
        raise ValueError("one probability per loan")

    approved_exposure = 0.0
    reported = 0.0
    realized = 0.0
    value = 0.0
    approved = 0
    defaults_approved = 0
    rejected_good_count = 0
    rejected_good_exposure = 0.0
    forgone = 0.0
    avoided = 0.0

    for p, loan in zip(preds, loans):
        ead = loan.exposure
        if p <= cutoff:
            approved += 1
            approved_exposure += ead
            defaults_approved += loan.defaulted
            reported += p * ead * lgd
            realized += loan.defaulted * ead * lgd
            value += margin * ead - lgd * ead * loan.defaulted
        elif loan.defaulted:
            avoided += lgd * ead
        else:
            rejected_good_count += 1
            rejected_good_exposure += ead
            forgone += margin * ead

    n = len(loans)
    return PolicyResult(
        cutoff=cutoff,
        approved=approved,
        approval_rate=approved / n,
        approved_exposure=approved_exposure,
        defaults_approved=defaults_approved,
        realized_default_rate=(defaults_approved / approved) if approved else 0.0,
        reported_expected_loss=reported,
        realized_loss=realized,
        loss_multiple=(reported / realized) if realized else 0.0,
        value=value,
        rejected_good_count=rejected_good_count,
        rejected_good_exposure=rejected_good_exposure,
        forgone_contribution=forgone,
        avoided_loss=avoided,
    )
