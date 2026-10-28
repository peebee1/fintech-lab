"""Exact allocation and FX rounding for payments.

One amount, several parties, currencies with different minor unit exponents. The
package answers three questions with numbers: whether an allocation preserves the
total, whether the FX conversion order changes the settlement, and where float64 and
exact decimal arithmetic disagree.
"""

from . import alloc, bench, fx, money, rounding

__all__ = ["alloc", "bench", "fx", "money", "rounding"]
