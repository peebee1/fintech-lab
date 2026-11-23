# Replay

Seed 20261123, 60 days, 49,752 transactions, EUR 2,953,266.79 processed, latent fraud 14.16 bps of value.

| policy | exempt % txn | exempt % value | challenges | abandoned | fraud loss | friction | total | breach days |
|---|---|---|---|---|---|---|---|---|
| challenge_all | 0 | 0.0% | 49,752 | 2,854 | 324 | 34,619 | 34,943 | 0 |
| low_value_only | 40 | 11.5% | 29,911 | 1,619 | 511 | 30,047 | 30,558 | 0 |
| tra_tight | 55 | 27.5% | 22,627 | 1,229 | 625 | 24,402 | 25,026 | 0 |
| tra_risk_cutoff | 71 | 52.2% | 14,556 | 789 | 794 | 15,646 | 16,439 | 8 |
| tra_no_risk_test | 78 | 57.1% | 11,125 | 594 | 2,312 | 14,540 | 16,852 | 14 |
| flat_etv_500 | 100 | 96.3% | 154 | 7 | 4,165 | 1,028 | 5,193 | 56 |
| exempt_everything | 100 | 100.0% | 0 | 0 | 4,710 | 0 | 4,710 | 56 |

Costs in EUR. Friction is lost contribution margin on abandoned checkouts.
