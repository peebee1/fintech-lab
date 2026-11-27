# Seller payout bench

Synthetic book, seed 20261127, 180 days, 400 sellers, 52,349 orders, 1,932 refunds, $6,927,844.81 GMV, refund cost $254,124.66.

| Policy | Hold | Reserve | Write-off | Float cost | Economic | Write-off bps | Economic bps | Sellers written off |
|---|---|---|---|---|---|---|---|---|
| pay_t1 | 1 | none | $57,605.04 | $2,260.84 | $59,865.88 | 83.15 | 86.41 | 263 |
| hold_7 | 7 | none | $45,062.09 | $15,880.07 | $60,942.16 | 65.04 | 87.97 | 231 |
| hold_14 | 14 | none | $33,537.86 | $31,813.71 | $65,351.57 | 48.41 | 94.33 | 189 |
| hold_21 | 21 | none | $24,979.60 | $47,726.18 | $72,705.78 | 36.06 | 104.95 | 156 |
| reserve_5 | 1 | 5.0% / 30d | $35,177.93 | $5,444.98 | $40,622.91 | 50.78 | 58.64 | 204 |
| reserve_10 | 1 | 10.0% / 30d | $25,911.97 | $8,879.54 | $34,791.51 | 37.40 | 50.22 | 166 |
| reserve_20 | 1 | 20.0% / 30d | $19,854.90 | $15,771.16 | $35,626.06 | 28.66 | 51.42 | 136 |
| hold_7_reserve_10 | 7 | 10.0% / 30d | $19,617.11 | $22,654.52 | $42,271.63 | 28.32 | 61.02 | 139 |
| reserve_10_no_clawback | 1 | 10.0% / 30d | $28,162.29 | $8,879.54 | $37,041.83 | 40.65 | 53.47 | 173 |
| tiered_hold | banded | banded | $28,282.07 | $29,323.46 | $57,605.53 | 40.82 | 83.15 | 155 |
| tiered_reserve | banded | banded | $29,260.88 | $19,420.24 | $48,681.12 | 42.24 | 70.27 | 165 |
| oracle | exact | exact | $0.00 | $8,226.01 | $8,226.01 | 0.00 | 11.87 | 0 |

## Reserve sweep at a one day payout

| Reserve rate | Reserve days | Write-off | Float cost | Economic | Write-off bps |
|---|---|---|---|---|---|
| 0.0% | 30 | $57,605.04 | $2,260.84 | $59,865.88 | 83.15 |
| 5.0% | 30 | $35,177.93 | $5,444.98 | $40,622.91 | 50.78 |
| 10.0% | 30 | $25,911.97 | $8,879.54 | $34,791.51 | 37.40 |
| 15.0% | 30 | $21,835.52 | $12,329.06 | $34,164.58 | 31.52 |
| 20.0% | 30 | $19,854.90 | $15,771.16 | $35,626.06 | 28.66 |
| 25.0% | 30 | $18,830.34 | $19,204.63 | $38,034.97 | 27.18 |
| 30.0% | 30 | $18,361.23 | $22,634.36 | $40,995.59 | 26.50 |

## Marginal return per five points of reserve

| From | To | Write-off saved | Float added | Net |
|---|---|---|---|---|
| 0.0% | 5.0% | $22,427.11 | $3,184.14 | $19,242.97 |
| 5.0% | 10.0% | $9,265.96 | $3,434.56 | $5,831.40 |
| 10.0% | 15.0% | $4,076.45 | $3,449.52 | $626.93 |
| 15.0% | 20.0% | $1,980.62 | $3,442.10 | $-1,461.48 |
| 20.0% | 25.0% | $1,024.56 | $3,433.47 | $-2,408.91 |
| 25.0% | 30.0% | $469.11 | $3,429.73 | $-2,960.62 |

## Hold sweep at zero reserve

| Hold days | Write-off | Float cost | Economic | Write-off bps |
|---|---|---|---|---|
| 0 | $59,446.83 | $0.00 | $59,446.83 | 85.81 |
| 3 | $53,731.97 | $6,791.01 | $60,522.98 | 77.56 |
| 7 | $45,062.09 | $15,880.07 | $60,942.16 | 65.04 |
| 14 | $33,537.86 | $31,813.71 | $65,351.57 | 48.41 |
| 21 | $24,979.60 | $47,726.18 | $72,705.78 | 36.06 |
| 28 | $19,647.75 | $63,621.66 | $83,269.41 | 28.36 |

## The same claims on other books

| Seed | GMV | Pay T+1 write-off | Pay T+1 economic | Best flat | Best flat economic | Tiered hold economic | Oracle | Prize captured |
|---|---|---|---|---|---|---|---|---|
| 20261127 | $6,927,844.81 | $57,605.04 | $59,865.88 | reserve_15 | $34,164.58 | $57,605.53 | $8,226.01 | 49.8% |
| 20261128 | $6,878,626.82 | $56,675.93 | $58,921.37 | reserve_15 | $35,283.32 | $56,663.86 | $8,006.77 | 46.4% |
| 20261129 | $7,007,643.11 | $59,500.98 | $61,788.78 | reserve_15 | $38,856.73 | $58,367.52 | $8,458.65 | 43.0% |

## Comparison

- Zero reserve write-off is $57,605.04. A 10 percent reserve cuts it 55.0 percent.
- The best flat rung is reserve_15 at $34,164.58, writing off $21,835.52 for $12,329.06 of float.
- The banded hold policy costs $57,605.53, $23,440.95 more than the best flat rung. The banded reserve policy costs $48,681.12, $14,516.54 more.
- A 14 day hold writes off $33,537.86 for $31,813.71 of float; a 10 percent reserve writes off $25,911.97 for $8,879.54.
- Clawback from later payouts is worth $2,250.32 of write-off at the same reserve rate.
- The oracle writes off $0.00 at $8,226.01, prize $51,639.87, and the best flat rung captures 49.8 percent of it.

## Checks

All checks pass.
