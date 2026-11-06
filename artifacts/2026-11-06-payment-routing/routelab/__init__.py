"""Authorization-rate aware payment routing.

A simulator for the decision every high volume merchant makes on every checkout:
which acquirer or PSP should see this transaction. The fee schedule is on the
contract. The approval rate is not.
"""

__all__ = ["data", "psps", "outcomes", "policies", "bench"]
