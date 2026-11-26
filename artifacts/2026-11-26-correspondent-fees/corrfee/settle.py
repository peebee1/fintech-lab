"""The replay: apply a charge code to every invoice and write a ledger row.

One row per invoice. The row carries what the sender paid, what the chain took,
what arrived, and who absorbed the difference. Two independent sums are kept so
the partition can be asserted rather than assumed:

    sender_outlay  = fee + repair + repair_fee + ops
    economic_cost  = sender_outlay + supplier_absorbed
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .book import Book, Invoice
from .fees import our_fee, sender_bank_fee, sha_fee
from .policies import Policy

CLAIM_OPS_CENTS = 1_800
TOLERANCE_BPS = 5
TOLERANCE_MIN_CENTS = 2_500


@dataclass(frozen=True)
class Row:
    invoice_id: str
    corridor: str
    amount_cents: int
    code: str
    sender_fee_cents: int
    deductions_cents: int
    delivered_cents: int
    shortfall_cents: int
    tolerance_cents: int
    claimed: bool
    repaired: bool
    repair_fee_cents: int
    ops_cents: int

    @property
    def supplier_cents(self) -> int:
        """The part of the shortfall the beneficiary ends up carrying."""
        return 0 if self.repaired else self.shortfall_cents

    @property
    def sender_outlay_cents(self) -> int:
        repair = self.shortfall_cents if self.repaired else 0
        return self.sender_fee_cents + repair + self.repair_fee_cents + self.ops_cents

    @property
    def economic_cents(self) -> int:
        return self.sender_outlay_cents + self.supplier_cents


@dataclass
class Result:
    policy: str
    code: str
    note: str
    rows: list[Row] = field(default_factory=list)

    def _sum(self, name: str) -> int:
        return sum(getattr(row, name) for row in self.rows)

    @property
    def invoices(self) -> int:
        return len(self.rows)

    @property
    def value_cents(self) -> int:
        return self._sum("amount_cents")

    @property
    def delivered_cents(self) -> int:
        return self._sum("delivered_cents")

    @property
    def shortfall_cents(self) -> int:
        return self._sum("shortfall_cents")

    @property
    def sender_fee_cents(self) -> int:
        return self._sum("sender_fee_cents")

    @property
    def repair_cents(self) -> int:
        return sum(row.shortfall_cents for row in self.rows if row.repaired)

    @property
    def repair_fee_cents(self) -> int:
        return self._sum("repair_fee_cents")

    @property
    def ops_cents(self) -> int:
        return self._sum("ops_cents")

    @property
    def sender_total_cents(self) -> int:
        return sum(row.sender_outlay_cents for row in self.rows)

    @property
    def supplier_cents(self) -> int:
        return sum(row.supplier_cents for row in self.rows)

    @property
    def economic_cents(self) -> int:
        return self.sender_total_cents + self.supplier_cents

    @property
    def claims(self) -> int:
        return sum(1 for row in self.rows if row.claimed)

    @property
    def repairs(self) -> int:
        return sum(1 for row in self.rows if row.repaired)

    @property
    def declined(self) -> int:
        return sum(1 for row in self.rows if row.claimed and not row.repaired)

    @property
    def tolerated(self) -> int:
        return sum(1 for row in self.rows if not row.claimed and row.shortfall_cents > 0)

    @property
    def sender_bps(self) -> float:
        return 0.0 if self.value_cents == 0 else round(
            self.sender_total_cents * 10_000 / self.value_cents, 3
        )

    @property
    def economic_bps(self) -> float:
        return 0.0 if self.value_cents == 0 else round(
            self.economic_cents * 10_000 / self.value_cents, 3
        )

    def by_corridor(self) -> list[dict]:
        out = []
        for code in sorted({row.corridor for row in self.rows}):
            rows = [row for row in self.rows if row.corridor == code]
            value = sum(row.amount_cents for row in rows)
            sender = sum(row.sender_outlay_cents for row in rows)
            supplier = sum(row.supplier_cents for row in rows)
            out.append(
                {
                    "corridor": code,
                    "invoices": len(rows),
                    "value_cents": value,
                    "sender_cents": sender,
                    "supplier_cents": supplier,
                    "economic_cents": sender + supplier,
                    "sender_bps": 0.0 if value == 0 else round(sender * 10_000 / value, 3),
                    "economic_bps": 0.0
                    if value == 0
                    else round((sender + supplier) * 10_000 / value, 3),
                    "claims": sum(1 for row in rows if row.claimed),
                }
            )
        return out


def apply_code(code: str, invoice: Invoice) -> tuple[int, int, int]:
    """Return (sender fee, deductions taken off the amount, delivered)."""
    amount = invoice.amount_cents
    chain = invoice.deductions_cents
    if code == "OUR":
        return our_fee(amount), 0, amount
    if code == "SHA":
        return sha_fee(amount), chain, amount - chain
    own = sender_bank_fee(amount)
    return 0, chain + own, amount - chain - own


def tolerance_for(amount_cents: int, tolerance_bps: int, tolerance_min: int) -> int:
    return max(tolerance_min, amount_cents * tolerance_bps // 10_000)


def settle(
    book: Book,
    policy: Policy,
    context: dict | None = None,
    tolerance_bps: int = TOLERANCE_BPS,
    tolerance_min: int = TOLERANCE_MIN_CENTS,
) -> Result:
    ctx = context or {}
    result = Result(policy=policy.name, code=policy.code, note=policy.note)
    for invoice in book.invoices:
        code = policy.code_for(invoice, ctx)
        fee, deductions, delivered = apply_code(code, invoice)
        shortfall = invoice.amount_cents - delivered
        if shortfall < 0:
            raise ValueError(f"{invoice.id}: delivered more than instructed")
        tolerance = tolerance_for(invoice.amount_cents, tolerance_bps, tolerance_min)
        claimed = shortfall > tolerance
        repaired = claimed and policy.wants_repair(shortfall)
        repair_fee = our_fee(shortfall) if repaired else 0
        result.rows.append(
            Row(
                invoice_id=invoice.id,
                corridor=invoice.corridor,
                amount_cents=invoice.amount_cents,
                code=code,
                sender_fee_cents=fee,
                deductions_cents=deductions,
                delivered_cents=delivered,
                shortfall_cents=shortfall,
                tolerance_cents=tolerance,
                claimed=claimed,
                repaired=repaired,
                repair_fee_cents=repair_fee,
                ops_cents=CLAIM_OPS_CENTS if claimed else 0,
            )
        )
    return result
