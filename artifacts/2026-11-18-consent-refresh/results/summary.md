# Results

Book: 1200 synthetic payers across 12 merchants, 360 days, 13834 scheduled debits, USD 525,635.54 billed. Consent lifetime 90 days. Median bill USD 32.65, median re-auth latency 20.4 hours, mean walk-away 11.6% per prompt.

Reference ceiling: USD 473,680.11 captured with consents that never expire, which no rail allows. Natural churn still applies.

## Policies

| Policy | Settled | Refused | Refused USD | Captured USD | Capture rate | Prompts | Prompts/payer | Contextual | Abandon per prompt | USD per prompt |
|---|---|---|---|---|---|---|---|---|---|---|
| never_refresh | 3548 | 9007 | 339,382.93 | 134,297.18 | 28.3% | 0 | 0.0 | 0.0% | 0.0% | - |
| on_failure | 8279 | 2322 | 87,972.04 | 312,873.07 | 66.0% | 1990 | 1.66 | 0.1% | 17.8% | 157.22 |
| fixed_30 | 6403 | 0 | 0.00 | 241,699.56 | 51.0% | 7669 | 6.39 | 10.2% | 10.3% | 31.52 |
| fixed_90 | 9226 | 39 | 1,560.38 | 349,661.46 | 73.8% | 3741 | 3.12 | 6.8% | 11.5% | 93.47 |
| jit_1 | 10089 | 1590 | 60,239.29 | 380,585.24 | 80.3% | 2789 | 2.32 | 100.0% | 6.7% | 136.46 |
| jit_2 | 11012 | 687 | 26,937.41 | 418,007.49 | 88.2% | 2963 | 2.47 | 100.0% | 5.6% | 141.08 |
| jit_3 | 11334 | 350 | 13,383.83 | 424,678.49 | 89.7% | 3024 | 2.52 | 100.0% | 5.8% | 140.44 |
| jit_7 | 10676 | 66 | 2,210.78 | 401,479.08 | 84.8% | 2889 | 2.41 | 0.0% | 11.6% | 138.97 |
| adaptive_lead | 10853 | 173 | 6,259.31 | 408,803.52 | 86.3% | 2919 | 2.43 | 47.1% | 9.1% | 140.05 |

## Lead time sweep (just in time)

| Lead days | Refused | Captured USD | Capture rate | Prompts | Contextual share |
|---|---|---|---|---|---|
| 1 | 1590 | 380,585.24 | 80.3% | 2789 | 100.0% |
| 2 | 687 | 418,007.49 | 88.2% | 2963 | 100.0% |
| 3 | 350 | 424,678.49 | 89.7% | 3024 | 100.0% |
| 4 | 197 | 394,185.30 | 83.2% | 2834 | 0.0% |
| 5 | 125 | 407,128.04 | 86.0% | 2905 | 0.0% |
| 6 | 99 | 401,419.69 | 84.7% | 2864 | 0.0% |
| 7 | 66 | 401,479.08 | 84.8% | 2889 | 0.0% |
| 8 | 45 | 410,019.83 | 86.6% | 2914 | 0.0% |
| 9 | 35 | 410,839.41 | 86.7% | 2923 | 0.0% |
| 10 | 24 | 405,182.09 | 85.5% | 2880 | 0.0% |
| 11 | 16 | 406,830.88 | 85.9% | 2906 | 0.0% |
| 12 | 18 | 408,695.44 | 86.3% | 2917 | 0.0% |

## Stress: contextual prompts convert no better (multiplier 1.0)

| Policy | Captured USD | Capture rate | Refused | Prompts |
|---|---|---|---|---|
| fixed_30 | 235,843.05 | 49.8% | 0 | 7627 |
| jit_2 | 385,737.42 | 81.4% | 653 | 2813 |
| jit_7 | 401,479.08 | 84.8% | 66 | 2889 |
| adaptive_lead | 399,545.79 | 84.4% | 159 | 2868 |

## Stress: re-auth responses 1.5x slower

| Policy | Captured USD | Capture rate | Refused | Prompts |
|---|---|---|---|---|
| fixed_30 | 252,918.20 | 53.4% | 0 | 7788 |
| jit_2 | 406,102.38 | 85.7% | 1072 | 2903 |
| jit_7 | 403,306.34 | 85.1% | 167 | 2887 |
| adaptive_lead | 406,499.17 | 85.8% | 301 | 2916 |

## Checks

| Check | Result |
|---|---|
| every_attempt_accounted | pass |
| no_settlement_on_expired_consent | pass |
| jit_prompts_all_have_a_payment_at_risk | pass |
| never_refresh_sends_no_prompts | pass |
| ceiling_binds | pass |
| dropoff_binds | pass |
| contextual_conversion_shows | pass |
| lead_time_binds | pass |
| calendar_is_worse_than_jit | pass |
| deterministic | pass |

Settlements audited against a replay of the logged consent timeline: never_refresh 3548, on_failure 8279, fixed_30 6403, fixed_90 9226, jit_1 10089, jit_2 11012, jit_3 11334, jit_7 10676, adaptive_lead 10853 settlements, 0 on an expired consent.
