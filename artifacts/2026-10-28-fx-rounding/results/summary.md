## Allocation over synthetic payouts

seed 20261028, 3000 payouts, currencies USD, JPY, KWD.

| Method | Unbalanced | Rate | Overpaid | Underpaid | Worst gap (minor) |
|---|---|---|---|---|---|
| largest_remainder | 0 | 0.0% | 0 | 0 | 0 |
| floor_to_largest | 0 | 0.0% | 0 | 0 | 0 |
| naive_half_up | 621 | 20.7% | 317 | 304 | 2 |
| naive_half_even | 622 | 20.73% | 315 | 307 | 2 |

| Currency | Minor digits | naive_half_up unbalanced | largest_remainder unbalanced |
|---|---|---|---|
| USD | 2 | 19.63% | 0.0% |
| JPY | 0 | 22.43% | 0.0% |
| KWD | 3 | 20.02% | 0.0% |

## Who gets the benefit

Same size, separate draw of 3000 payouts. Excess is the largest party's allocation minus that party's exact share, in basis points of the payout.

| Method | Largest party overpaid | Rate | Mean excess (bps) | Worst excess (bps) | Worst excess (minor) |
|---|---|---|---|---|---|
| largest_remainder | 1413 | 47.1% | -0.01 | 38.2 | 0.757019 |
| floor_to_largest | 2871 | 95.7% | 0.84 | 876.57 | 3.299138 |
| naive_half_up | 1399 | 46.63% | 0.01 | 38.2 | 0.5 |
| naive_half_even | 1394 | 46.47% | 0.01 | 38.2 | 0.5 |

## Convert then split against split then convert

EUR source, 3000 payouts, exact decimal rates.

| Target | Payouts | Disagreed | Rate | Over | Under | Worst gap (minor) |
|---|---|---|---|---|---|---|
| USD | 1007 | 338 | 33.57% | 174 | 164 | 2 |
| JPY | 997 | 324 | 32.5% | 158 | 166 | 2 |
| KWD | 996 | 326 | 32.73% | 160 | 166 | 2 |

## Exhaustive invariants

3374 cases: 241 totals (0 to 240) against 14 weight families.

| Check | Violations |
|---|---|
| largest_remainder preserves the total | 0 |
| per party deviation under one minor unit | 0 |
| residual equals explained gap | 0 |
| zero weight party receives nothing | 0 |
| naive_half_up loses the total | 1571 (46.56% of cases) |

## One worked example

10000 minor units of USD split by weights (1, 1, 1).

| Method | Parts | Sum | Residual |
|---|---|---|---|
| largest_remainder | (3334, 3333, 3333) | 10000 | 0 |
| floor_to_largest | (3334, 3333, 3333) | 10000 | 0 |
| naive_half_up | (3333, 3333, 3333) | 9999 | 1 |
| naive_half_even | (3333, 3333, 3333) | 9999 | 1 |
