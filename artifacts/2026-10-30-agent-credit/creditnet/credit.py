"""Three credit rules on the same flow: no limit, gross cap, net debit cap."""

from __future__ import annotations

from .ledger import Ledger, Obligation

UNLIMITED = "unlimited"
GROSS = "gross_cap"
NET = "net_cap"
RULES = (UNLIMITED, GROSS, NET)


class CreditBook:
    """Admits or refuses obligations against a per member limit for one window.

    The book tracks committed outflow and inflow from admitted obligations only,
    which is what the clearing house knows at decision time.
    """

    def __init__(self, limits: dict[str, int], rule: str) -> None:
        if rule not in RULES:
            raise ValueError(f"unknown rule: {rule}")
        if any(limit <= 0 for limit in limits.values()):
            raise ValueError("limits must be positive")
        self.limits = dict(limits)
        self.rule = rule
        self.ledger = Ledger()
        self.rejected: list[Obligation] = []
        self._out = {member: 0 for member in limits}
        self._in = {member: 0 for member in limits}

    def projected_net_debit(self, payer: str, amount: int) -> int:
        """What the payer would have to find at settlement if this is admitted."""
        return max(0, self._out[payer] + amount - self._in[payer])

    def _fits(self, obligation: Obligation) -> bool:
        limit = self.limits[obligation.payer]
        if self.rule == UNLIMITED:
            return True
        if self.rule == GROSS:
            return self._out[obligation.payer] + obligation.amount <= limit
        return self.projected_net_debit(obligation.payer, obligation.amount) <= limit

    def admit(self, obligation: Obligation) -> bool:
        if obligation.payer not in self.limits:
            raise KeyError(f"unknown payer: {obligation.payer}")
        if obligation.payee not in self.limits:
            raise KeyError(f"unknown payee: {obligation.payee}")
        if not self._fits(obligation):
            self.rejected.append(obligation)
            return False
        self.ledger.add(obligation)
        self._out[obligation.payer] += obligation.amount
        self._in[obligation.payee] += obligation.amount
        return True

    def max_net_debit(self) -> int:
        positions = self.ledger.net_positions()
        return max((max(0, -value) for value in positions.values()), default=0)

    def position(self, member: str) -> int:
        return self.ledger.net_positions().get(member, 0)

    def admitted_value(self) -> int:
        return self.ledger.gross_value()

    def rejected_value(self) -> int:
        return sum(ob.amount for ob in self.rejected)
