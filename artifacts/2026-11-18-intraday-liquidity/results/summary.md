# Intraday liquidity bench

Seed 20261118, 720 business days, 60 burn in, 660 scored.
Payout volume USD 1,369,861,695, net flow over the whole book USD 9,881.

## Sizing policies

| policy | mean opening USD | annual cost USD | of which carry | of which fees | of which facility | failed batches | days shorted |
|---|---|---|---|---|---|---|---|
| zero | 0 | 448,355 | 0 | 122,086 | 326,268 | 1279 | 100.0% |
| daily_net | 23,728 | 443,202 | 1,304 | 121,609 | 320,289 | 1274 | 100.0% |
| daily_net_p95 | 634,288 | 271,703 | 34,845 | 66,150 | 170,708 | 693 | 95.6% |
| gross_batch | 1,288,262 | 140,727 | 70,772 | 31,405 | 38,550 | 329 | 49.9% |
| peak_p50 | 1,266,671 | 136,331 | 69,586 | 33,982 | 32,763 | 356 | 53.9% |
| peak_p75 | 1,409,623 | 114,192 | 77,439 | 17,373 | 19,380 | 182 | 27.6% |
| peak_p90 | 1,609,061 | 106,970 | 88,395 | 8,018 | 10,556 | 84 | 12.7% |
| peak_p95 | 1,764,892 | 109,352 | 96,956 | 4,868 | 7,527 | 51 | 7.7% |
| peak_p100 | 2,436,813 | 137,985 | 133,869 | 1,623 | 2,493 | 17 | 2.6% |
| oracle | 1,294,716 | 71,127 | 71,127 | 0 | 0 | 0 | 0.0% |

## Percentile sweep

| quantile | mean opening USD | annual cost USD | failed batches | days shorted |
|---|---|---|---|---|
| peak_p50 | 1,266,671 | 136,331 | 356 | 356 |
| peak_p60 | 1,319,097 | 125,343 | 276 | 276 |
| peak_p70 | 1,374,486 | 116,515 | 202 | 202 |
| peak_p75 | 1,409,623 | 114,192 | 182 | 182 |
| peak_p80 | 1,460,585 | 110,437 | 145 | 145 |
| peak_p85 | 1,522,596 | 107,746 | 113 | 113 |
| peak_p90 | 1,609,061 | 106,970 | 84 | 84 |
| peak_p95 | 1,764,892 | 109,352 | 51 | 51 |
| peak_p100 | 2,436,813 | 137,985 | 17 | 17 |

## Trailing window at the ninetieth percentile

| window days | mean opening USD | annual cost USD | failed batches | days shorted |
|---|---|---|---|---|
| 20 | 1,596,818 | 107,714 | 93 | 93 |
| 40 | 1,609,061 | 106,970 | 84 | 84 |
| 80 | 1,610,789 | 106,879 | 84 | 84 |
| 160 | 1,631,600 | 106,540 | 76 | 76 |

## Fee sensitivity

| fee per failed batch USD | best policy | best annual USD | peak_p90 USD | peak_p100 USD |
|---|---|---|---|---|
| 50 | peak_p75 | 100,294 | 100,555 | 136,686 |
| 250 | peak_p90 | 106,970 | 106,970 | 137,985 |
| 1,000 | peak_p95 | 123,956 | 131,024 | 142,853 |

## Regimes

### baseline

4 percent of settlement days slip to the next morning

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 448,355 | 1279 |
| daily_net | 23,728 | 443,202 | 1274 |
| daily_net_p95 | 634,288 | 271,703 | 693 |
| gross_batch | 1,288,262 | 140,727 | 329 |
| peak_p50 | 1,266,671 | 136,331 | 356 |
| peak_p75 | 1,409,623 | 114,192 | 182 |
| peak_p90 | 1,609,061 | 106,970 | 84 |
| peak_p95 | 1,764,892 | 109,352 | 51 |
| peak_p100 | 2,436,813 | 137,985 | 17 |

### slip 12 percent

the acquirer delays three times as often

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 424,281 | 1226 |
| daily_net | 24,477 | 418,790 | 1219 |
| daily_net_p95 | 827,907 | 217,046 | 580 |
| gross_batch | 1,288,262 | 134,007 | 299 |
| peak_p50 | 1,239,143 | 134,195 | 345 |
| peak_p75 | 1,395,418 | 111,871 | 175 |
| peak_p90 | 1,586,221 | 104,788 | 80 |
| peak_p95 | 1,727,897 | 107,485 | 57 |
| peak_p100 | 2,359,777 | 133,704 | 15 |

### payout spikes 10 percent

more merchants batch quarterly payouts through the same cutoff

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 487,901 | 1279 |
| daily_net | 5,422 | 486,641 | 1277 |
| daily_net_p95 | 982,904 | 238,831 | 570 |
| gross_batch | 1,665,825 | 144,603 | 179 |
| peak_p50 | 1,322,709 | 165,035 | 333 |
| peak_p75 | 1,586,518 | 142,195 | 180 |
| peak_p90 | 2,069,219 | 141,337 | 86 |
| peak_p95 | 2,450,604 | 148,548 | 46 |
| peak_p100 | 3,125,617 | 176,070 | 16 |

### batch one is 60 percent

merchants move their cutoffs earlier in the day

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 449,978 | 1296 |
| daily_net | 23,728 | 445,302 | 1296 |
| daily_net_p95 | 634,288 | 288,694 | 871 |
| gross_batch | 1,704,373 | 114,401 | 103 |
| peak_p50 | 1,266,671 | 137,095 | 364 |
| peak_p75 | 1,409,623 | 114,478 | 185 |
| peak_p90 | 1,609,061 | 106,970 | 84 |
| peak_p95 | 1,764,892 | 109,352 | 51 |
| peak_p100 | 2,436,813 | 137,985 | 17 |

### settlement at the open

the acquirer settles the whole day at 08:00, before any payout

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 56,927 | 300 |
| daily_net | 22,985 | 52,992 | 273 |
| daily_net_p95 | 502,182 | 37,691 | 38 |
| gross_batch | 1,288,262 | 71,998 | 6 |
| peak_p50 | 2,429 | 56,819 | 300 |
| peak_p75 | 125,733 | 40,857 | 174 |
| peak_p90 | 295,917 | 33,638 | 73 |
| peak_p95 | 476,001 | 37,902 | 46 |
| peak_p100 | 1,085,744 | 63,881 | 19 |

### volume steps up 25 percent

a large merchant cohort goes live at business day 400

| policy | mean opening USD | annual cost USD | failed batches |
|---|---|---|---|
| zero | 0 | 487,280 | 1279 |
| daily_net | 26,460 | 481,588 | 1274 |
| daily_net_p95 | 710,638 | 296,199 | 693 |
| gross_batch | 1,442,801 | 154,483 | 330 |
| peak_p50 | 1,409,944 | 150,571 | 362 |
| peak_p75 | 1,572,382 | 126,898 | 189 |
| peak_p90 | 1,790,304 | 119,113 | 89 |
| peak_p95 | 1,956,636 | 121,425 | 55 |
| peak_p100 | 2,704,487 | 152,995 | 17 |

## Checks

- every_eval_day_scored: pass
- oracle_has_no_shortfall: pass
- oracle_is_the_floor: pass
- every_net_positive_day_still_shorts_at_zero: pass
- timing_policy_halves_the_daily_net_policy: pass
- carry_rises_with_the_percentile: pass
- retimed_settlement_needs_less_float: pass
- book_is_plausible: pass
- no_day_fails_more_than_two_batches: pass
