# ledger-close results

Bench clock: 2026-05-20T09:30:00Z. Seed 7. Synthetic book, no real data.

- book transactions: 281 (240 payment, 6 payout, 35 refund)
- gross processed: INR 6,375,195.38
- average payment: INR 26,563.31
- closed periods: 2026-01, 2026-02, 2026-03, 2026-04

## Closed period drift, reported total versus recomputed total

| period | sealed drift | baseline drift |
|---|---|---|
| 2026-01 | none | fee_revenue INR 5,000.00, tax_payable INR -5,000.00 |
| 2026-02 | none | cash INR 5,000.00, fee_revenue INR -4,000.00 |
| 2026-03 | none | bank_fees INR 1,850.00, cash INR -1,850.00 |
| 2026-04 | none | none |

## Refusals fired by the sealed ledger

| rule | count |
|---|---|
| ClosedPeriod | 2 |
| NoAmend | 1 |
| Unbalanced | 1 |

Idempotent replay appended 0 entries. The baseline accepted the same retry and credited INR 548.36 of fee revenue twice.

## Proofs

| check | sealed | baseline |
|---|---|---|
| closes reproducing after the events | 4/4 | 1/4 |
| periods balanced after the events | 6/6 | 4/6 |
| book nets to zero after the events | INR 0.00 | INR 2,000.00 |
| out of band edit detected | yes | no |

The edited entry breaks the chain at seq 1 (entry contents changed after it was chained) and moves INR 25,000.00 of January revenue. Closes that no longer reproduce: 2026-01.

Reproduce: `PYTHONPATH=. uv run python -m ledgerclose.cli bench` from this directory.
