"""Intraday liquidity buffer sizing for a card acquiring settlement float.

The artifact asks one question: how much cash must an operating account hold at
the open, when merchant payouts leave before the acquirer settlement arrives.
"""

__all__ = ["book", "policy", "sim", "bench"]
