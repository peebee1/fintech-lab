# Results

Book per week: 4000 synthetic payments, USD 1,671,976.24 total, median USD 136.26, p99 USD 4,304.82, max USD 56,127.80. Scored on 4 held out weeks.

Calibration: 28 days, 16000 payments, seed 20261101. Evaluation seeds: 20261116, 20261123, 20261130, 20261207. The calibrated policy never sees the evaluation weeks.

## Policies

| Policy | k median | lost USD | loss bps | false credits | median wait s | p95 wait s | within 60s | wait cost USD | total cost USD |
|---|---|---|---|---|---|---|---|---|---|
| credit_on_inclusion | 1.0 | 84,791.45 | 136.372 | 366 | 4 | 21 | 100.0% | 7.50 | 84,798.95 |
| fixed_12 | 12.0 | 13,912.83 | 22.376 | 58 | 26 | 153 | 80.0% | 57.61 | 13,970.44 |
| chain_defaults | 30.0 | 13,857.15 | 22.287 | 56 | 61 | 393 | 45.0% | 126.37 | 13,983.52 |
| ticket_tiers | 6.0 | 2,832.36 | 4.555 | 56 | 47 | 121 | 92.5% | 47.59 | 2,879.95 |
| calibrated | 35.0 | 202.64 | 0.326 | 3 | 93 | 344 | 3.1% | 143.26 | 345.90 |

## Loss by week

| Policy | 20261116 | 20261123 | 20261130 | 20261207 |
|---|---|---|---|---|
| credit_on_inclusion | 21,242.57 | 13,719.05 | 15,045.58 | 34,784.25 |
| fixed_12 | 3,586.28 | 5,002.41 | 3,259.45 | 2,064.69 |
| chain_defaults | 3,530.60 | 5,002.41 | 3,259.45 | 2,064.69 |
| ticket_tiers | 357.95 | 280.60 | 593.27 | 1,600.54 |
| calibrated | 0.00 | 0.00 | 28.67 | 173.97 |

## Loss by chain

| Policy | Chain | k median | false credits | lost USD | median wait s |
|---|---|---|---|---|---|
| credit_on_inclusion | base | 1.0 | 350 | 83,035.59 | 4 |
| credit_on_inclusion | polygon | 1.0 | 14 | 1,657.45 | 4 |
| credit_on_inclusion | ethereum | 1.0 | 2 | 98.41 | 19 |
| fixed_12 | base | 12.0 | 55 | 13,857.15 | 26 |
| fixed_12 | polygon | 12.0 | 3 | 55.68 | 26 |
| fixed_12 | ethereum | 12.0 | 0 | 0.00 | 151 |
| chain_defaults | base | 12.0 | 55 | 13,857.15 | 26 |
| chain_defaults | polygon | 30.0 | 1 | 0.00 | 62 |
| chain_defaults | ethereum | 32.0 | 0 | 0.00 | 391 |
| ticket_tiers | base | 23.0 | 52 | 2,678.27 | 47 |
| ticket_tiers | polygon | 23.0 | 3 | 55.68 | 47 |
| ticket_tiers | ethereum | 4.0 | 1 | 98.41 | 51 |
| calibrated | base | 46.0 | 3 | 202.64 | 93 |
| calibrated | polygon | 35.0 | 0 | 0.00 | 71 |
| calibrated | ethereum | 28.0 | 0 | 0.00 | 340 |

## Where the money is lost, by ticket band

| Policy | under_100 | 100_to_1000 | 1000_to_10000 | over_10000 |
|---|---|---|---|---|
| fixed_12 | 797.91 | 2,671.00 | 10,443.92 | 0.00 |
| ticket_tiers | 994.59 | 1,837.77 | 0.00 | 0.00 |
| calibrated | 69.16 | 133.48 | 0.00 | 0.00 |

## Stress: incidents 1.5x deeper than the calibration month

Same four weeks, same fork heights, every incident 1.5x deeper than anything the calibration month contained. Policies keep the k they were fitted with.

| Policy | lost USD | loss bps | false credits | median wait s |
|---|---|---|---|---|
| credit_on_inclusion | 123,974.86 | 199.392 | 385 | 4 |
| fixed_12 | 16,355.88 | 26.306 | 73 | 26 |
| chain_defaults | 16,002.61 | 25.737 | 70 | 61 |
| ticket_tiers | 5,321.96 | 8.559 | 74 | 47 |
| calibrated | 6,740.41 | 10.841 | 38 | 93 |

## Fixed k sweep, pooled over the four weeks

| k | lost USD | loss bps | false credits | median wait s | p95 wait s | within 60s |
|---|---|---|---|---|---|---|
| 1 | 84,791.45 | 136.372 | 366 | 4 | 21 | 100.0% |
| 2 | 32,145.95 | 51.701 | 149 | 6 | 33 | 100.0% |
| 4 | 24,960.01 | 40.144 | 103 | 10 | 57 | 100.0% |
| 8 | 14,529.40 | 23.368 | 68 | 18 | 105 | 80.0% |
| 12 | 13,912.83 | 22.376 | 58 | 26 | 153 | 80.0% |
| 16 | 13,645.94 | 21.947 | 54 | 34 | 201 | 80.0% |
| 24 | 8,257.78 | 13.281 | 40 | 50 | 297 | 79.6% |
| 32 | 6,608.34 | 10.628 | 33 | 66 | 393 | 0.0% |
| 40 | 359.19 | 0.578 | 9 | 82 | 489 | 0.0% |
| 48 | 0.00 | 0.0 | 0 | 98 | 585 | 0.0% |
| 64 | 0.00 | 0.0 | 0 | 130 | 777 | 0.0% |

## Checks

- every_credit_after_inclusion: pass
- every_loss_was_credited_first: pass
- control_binds: pass
- loss_is_a_subset_of_false_credits: pass
- risk_curve_monotone: pass
- calibration_has_events: pass
- four_weeks_scored: pass
- deterministic_rerun: pass
