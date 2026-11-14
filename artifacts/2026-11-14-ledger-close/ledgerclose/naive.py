"""The baseline: stored balances, editable postings, closes that are just timestamps.

This class exists to be measured against, not to be used. Every method is the shape most
ledgers start life with, and each one hides the same defect: the number you reported is a
snapshot of mutable state, so it can change after you reported it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MutableLedger:
    def __init__(self, clock=None) -> None:
        self._clock = clock or _utcnow
        self.postings: list[dict] = []
        self._closes: dict[str, dict] = {}
        self.balances: dict[str, int] = {}

    # -- writes ---------------------------------------------------------------

    def post(self, lines, business_date: date, *, idempotency_key: str | None = None) -> str:
        """No balance check, no closed period check, no dedupe. That is the point."""
        identifier = f"p{len(self.postings) + 1:06d}"
        postings = [[line.account, int(line.amount_minor)] for line in lines]
        self.postings.append({"id": identifier, "business_date": business_date, "lines": postings})
        for account, amount in postings:
            self.balances[account] = self.balances.get(account, 0) + amount
        return identifier

    def amend(self, entry_id: str, lines) -> None:
        """A correction that rewrites history in place."""
        for posting in self.postings:
            if posting["id"] == entry_id:
                for account, amount in posting["lines"]:
                    self.balances[account] = self.balances.get(account, 0) - amount
                posting["lines"] = [[line.account, int(line.amount_minor)] for line in lines]
                for account, amount in posting["lines"]:
                    self.balances[account] = self.balances.get(account, 0) + amount
                return
        raise KeyError(entry_id)

    def close(self, period: str) -> dict:
        record = {
            "period": period,
            "closed_at": self._clock().astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            "control_totals": self.control_totals(period),
        }
        self._closes[period] = record
        return record

    # -- reads ----------------------------------------------------------------

    def entries_in(self, period: str) -> list[dict]:
        return [posting for posting in self.postings if posting["business_date"].isoformat()[:7] == period]

    def control_totals(self, period: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for posting in self.entries_in(period):
            for account, amount in posting["lines"]:
                totals[account] = totals.get(account, 0) + amount
        return {account: amount for account, amount in sorted(totals.items()) if amount != 0}

    def recorded_totals(self, period: str) -> dict[str, int] | None:
        record = self._closes.get(period)
        return dict(record["control_totals"]) if record else None

    def drift(self, period: str) -> dict[str, int]:
        recorded = self.recorded_totals(period)
        if recorded is None:
            return {}
        now = self.control_totals(period)
        accounts = set(recorded) | set(now)
        return {
            account: now.get(account, 0) - recorded.get(account, 0)
            for account in sorted(accounts)
            if now.get(account, 0) != recorded.get(account, 0)
        }

    def trial_balance(self, period: str) -> dict:
        debit = credit = 0
        for posting in self.entries_in(period):
            for _account, amount in posting["lines"]:
                if amount > 0:
                    debit += amount
                else:
                    credit -= amount
        return {"debit_minor": debit, "credit_minor": credit, "balanced": debit == credit}

    def net_minor(self) -> int:
        """A real ledger sums to zero across the whole book. A stored balance one need not."""
        return sum(line_amount for posting in self.postings for _account, line_amount in posting["lines"])

    def verify(self) -> dict:
        return {"ok": True, "checked": 0, "broken_seq": None, "reason": "no chain to verify"}

    def close_reproduces(self, period: str) -> bool:
        recorded = self.recorded_totals(period)
        return recorded is not None and recorded == self.control_totals(period)
