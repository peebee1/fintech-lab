"""Obligations between agents, and the positions they leave behind."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Obligation:
    """One agent promising to pay another. Amount is minor units, positive."""

    id: int
    payer: str
    payee: str
    amount: int
    ts: int

    def __post_init__(self) -> None:
        if self.payer == self.payee:
            raise ValueError(f"self payment: {self.payer}")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive, got {self.amount}")


class Ledger:
    """An append only set of admitted obligations."""

    def __init__(self) -> None:
        self._items: list[Obligation] = []

    def add(self, obligation: Obligation) -> None:
        self._items.append(obligation)

    def __iter__(self) -> Iterator[Obligation]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> tuple[Obligation, ...]:
        return tuple(self._items)

    def members(self) -> tuple[str, ...]:
        names = {ob.payer for ob in self._items} | {ob.payee for ob in self._items}
        return tuple(sorted(names))

    def gross_value(self) -> int:
        return sum(ob.amount for ob in self._items)

    def outflow(self, member: str) -> int:
        return sum(ob.amount for ob in self._items if ob.payer == member)

    def inflow(self, member: str) -> int:
        return sum(ob.amount for ob in self._items if ob.payee == member)

    def net_positions(self) -> dict[str, int]:
        """Positive means the member is owed at settlement, negative means it pays."""
        positions: dict[str, int] = {}
        for ob in self._items:
            positions[ob.payee] = positions.get(ob.payee, 0) + ob.amount
            positions[ob.payer] = positions.get(ob.payer, 0) - ob.amount
        return positions

    def bilateral(self) -> dict[tuple[str, str], int]:
        """Signed balance per ordered pair: positive means the first party is owed."""
        pairs: dict[tuple[str, str], int] = {}
        for ob in self._items:
            pairs[(ob.payer, ob.payee)] = pairs.get((ob.payer, ob.payee), 0) + ob.amount
        return pairs

    def imbalance(self) -> int:
        """Sum of every position. Anything other than zero is a broken ledger."""
        return sum(self.net_positions().values())
