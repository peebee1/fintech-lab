```
synthetic market: 12 agents, 20 windows, limit $600.00 per member per window

gross flow            $215,945.19
bilateral netting     $67,465.48  (-68.76%)
multilateral netting  $11,687.43  (-94.59%)
every window balances True

rule          admitted         value   share  worst debit   worst loss
unlimited         3000   $215,945.19  100.0%      $420.33      $420.33
gross_cap         1697   $138,171.37   64.0%      $520.47      $390.31
net_cap           3000   $215,945.19  100.0%      $420.33      $420.33

largest debtor pays $217.20 net, after sending $935.80 gross (4.8x)
fund to cover the worst window: $420.33 net debit (no limit rule: $420.33)
the $600.00 limit covers the worst loss: True
```
