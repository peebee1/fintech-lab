"""Settlement finality policy for stablecoin payments.

Credit a merchant before the chain is final and the chain can take the money back.
Wait for a fixed confirmation count and small tickets wait as long as large ones.
"""

from .chain import CHAINS, Chain, Reorg, generate_reorgs
from .book import Payment, build_book
from .policy import POLICIES, confirmations

__all__ = [
    "CHAINS",
    "Chain",
    "Reorg",
    "generate_reorgs",
    "Payment",
    "build_book",
    "POLICIES",
    "confirmations",
]
