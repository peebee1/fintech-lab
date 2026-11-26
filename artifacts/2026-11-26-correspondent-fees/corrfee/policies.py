"""Policies: a charge code, and what to do when a deduction claim arrives.

A policy is a pure function of the invoice and the context it is allowed to
know. It never sees the number of hops' fees on the invoice it is pricing,
except where the chooser is deliberately the oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .book import Invoice

Chooser = Callable[[Invoice, dict], str]


@dataclass(frozen=True)
class Policy:
    name: str
    code: str
    repair: str
    threshold_cents: int = 0
    chooser: Chooser | None = None
    note: str = ""

    def code_for(self, invoice: Invoice, context: dict) -> str:
        if self.chooser is None:
            return self.code
        return self.chooser(invoice, context)

    def wants_repair(self, shortfall_cents: int) -> bool:
        if self.repair == "never":
            return False
        if self.repair == "claims":
            return True
        return shortfall_cents > self.threshold_cents


def ladder() -> list[Policy]:
    """The nine policies, ordered from the worst default to the upper bound."""
    return [
        Policy("ben_all", "BEN", "never", note="beneficiary pays everything"),
        Policy("sha_none", "SHA", "never", note="shared, and nobody chases the shortfall"),
        Policy(
            "sha_claim_100", "SHA", "above", 10_000, note="top up claims over USD 100"
        ),
        Policy("sha_claim_50", "SHA", "above", 5_000, note="top up claims over USD 50"),
        Policy("sha_repair_all", "SHA", "claims", note="top up every claim"),
        Policy("our_all", "OUR", "never", note="one bundled charge, full delivery"),
        Policy("corridor_rule", "SHA", "never", note="OUR on the corridors that lose"),
        Policy("cost_rule", "SHA", "never", note="OUR when the expected deduction wins"),
        Policy("oracle", "SHA", "never", note="per invoice best, knowing the chain"),
    ]


BY_NAME = {policy.name: policy for policy in ladder()}
