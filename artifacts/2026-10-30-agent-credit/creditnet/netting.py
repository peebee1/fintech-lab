"""Multilateral netting: one settlement instruction per member, if the set holds."""

from __future__ import annotations

from dataclasses import dataclass

from .ledger import Ledger


@dataclass(frozen=True, slots=True)
class Instruction:
    payer: str
    payee: str
    amount: int


def settlement(ledger: Ledger) -> tuple[Instruction, ...]:
    """Debtors pay creditors. Total instructed equals total credited, by construction."""
    positions = ledger.net_positions()
    debtors = sorted((member, -value) for member, value in positions.items() if value < 0)
    creditors = sorted((member, value) for member, value in positions.items() if value > 0)
    owed = [amount for _, amount in debtors]
    due = [amount for _, amount in creditors]
    instructions: list[Instruction] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(owed[i], due[j])
        if amount > 0:
            instructions.append(Instruction(debtors[i][0], creditors[j][0], amount))
        owed[i] -= amount
        due[j] -= amount
        if owed[i] == 0:
            i += 1
        if due[j] == 0:
            j += 1
    return tuple(instructions)


def settlement_value(ledger: Ledger) -> int:
    """Money that actually moves after netting."""
    return sum(order.amount for order in settlement(ledger))


def reduction(ledger: Ledger) -> float:
    """Share of gross value that netting removes from the payment rails."""
    gross = ledger.gross_value()
    if gross == 0:
        return 0.0
    return 1.0 - settlement_value(ledger) / gross


def bilateral_settlement_value(ledger: Ledger) -> int:
    """The middle ground: net each pair, then settle every pair separately."""
    total = 0
    seen: set[tuple[str, str]] = set()
    pairs = ledger.bilateral()
    for (payer, payee), amount in pairs.items():
        key = (payer, payee) if payer < payee else (payee, payer)
        if key in seen:
            continue
        seen.add(key)
        reverse = pairs.get((key[1], key[0]), 0)
        total += abs(amount - reverse)
    return total
