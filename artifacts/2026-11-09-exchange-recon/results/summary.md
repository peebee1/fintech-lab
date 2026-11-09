```
session: 1668 prints, 992 orders with fills, 286 injected breaks, 280 orders flagged

policy           breaks   prec recall   gap sh     gap INR   cash INR
broker_only           0   0.00   0.00      844   2,720,292        n/a
broker_vs_app       206   0.43   0.31     1424   3,303,826        n/a
stream_replay        40   1.00   0.14     1779   3,434,396   -554,078
tape_three_way      286   1.00   1.00        0           0          0

per class, tape_three_way
  duplicate_fill        40/40   precision 1.00 recall 1.00
  missing_fill          40/40   precision 1.00 recall 1.00
  price_drift           40/40   precision 1.00 recall 1.00
  qty_mismatch          40/40   precision 1.00 recall 1.00
  broker_qty_lag        40/40   precision 1.00 recall 1.00
  fill_after_cancel     40/40   precision 1.00 recall 1.00
  orphan_fill           40/40   precision 1.00 recall 1.00
  phantom_position       6/6    precision 1.00 recall 1.00

explained shares 1231, max gap 0 across 6 symbols, cash gap 0 paise
sign flip sensitivity: 302 shares

triage 286 breaks, budget 60: impact order 87%, arrival 26%, random 20%, top ten 41%
total exposure INR 14,749,857
```
