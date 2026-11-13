```
synthetic book, seed 13, 6000 loans, 69,532,319 exposure
holdout 1500 loans, break even PD 0.0954

AUC is identical across all three models: 0.7402

model            brier    logloss   ece10   approval   value
scorecard        0.1074   0.3551    0.0195  0.4827     267,123
overconfident    0.1171   0.4751    0.0951  0.8587     -150,633
hedged           0.1193   0.4002    0.1123  0.0193     16,362

after Platt scaling on the calibration slice
scorecard        0.1067   0.3542    0.0213  0.4527     270,379
overconfident    0.1067   0.3542    0.0213  0.4527     270,379
hedged           0.1067   0.3542    0.0213  0.4527     270,379

overconfident brier 0.1171 vs calibrated 0.1074 (+9.1%)
platt cut brier by 8.8% and ece from 0.0951 to 0.0213
policy value gap 417,755, closed 100.8% by recalibration
reported loss multiple before 0.136, after 1.377
```
