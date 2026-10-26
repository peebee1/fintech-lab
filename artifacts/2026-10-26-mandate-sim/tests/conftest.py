import sys
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1]
if str(ARTIFACT) not in sys.path:
    sys.path.insert(0, str(ARTIFACT))

from mandate.model import Invoice, Population, Subscriber  # noqa: E402


def make_book(
    invoices: list[Invoice],
    subscribers: list[Subscriber],
    short_days: dict[str, frozenset[int]] | None = None,
    claim_draw: float = 1.0,
    afa_approved: bool = True,
    horizon_days: int = 90,
) -> Population:
    """A hand built book, so a test asserts one behaviour instead of a population."""
    return Population(
        subscribers=tuple(subscribers),
        invoices=tuple(invoices),
        short_days=short_days or {sub.id: frozenset() for sub in subscribers},
        afa_approved={(inv.id, index): afa_approved for inv in invoices for index in range(4)},
        claim_draw={inv.id: claim_draw for inv in invoices},
        horizon_days=horizon_days,
        seed=0,
    )


@pytest.fixture
def book():
    return make_book


@pytest.fixture
def one(book):
    """One subscriber, one invoice, one rail."""

    def _one(rail: str, amount: int = 1999, issued: int = 0, due: int = 20):
        sub = Subscriber(id="s1", rail=rail, amount_minor=amount, due_day=due)
        invoice = Invoice(
            id="i1",
            subscriber_id="s1",
            rail=rail,
            amount_minor=amount,
            issued_day=issued,
            due_day=due,
            cycle=0,
        )
        return book([invoice], [sub])

    return _one
