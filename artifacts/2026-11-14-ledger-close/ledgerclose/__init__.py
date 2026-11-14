"""Append only ledger with a provable close."""

from .ledger import CloseRecord, Ledger, Refusal, TrialBalance, period_of

__all__ = ["CloseRecord", "Ledger", "Refusal", "TrialBalance", "inr", "period_of"]


def inr(minor: int) -> str:
    sign = "-" if minor < 0 else ""
    whole, part = divmod(abs(minor), 100)
    return f"INR {sign}{whole:,}.{part:02d}"
