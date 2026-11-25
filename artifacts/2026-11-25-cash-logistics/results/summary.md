# Cash logistics bench

Synthetic network, seed 20261125, 120 days, 60 machines, 6,144,545 notes dispensed (INR 3,072,272,500.00).

| Policy | Trips | Emergency | Service | Held notes | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|---|
| fixed_week_capacity | 1029 | 0 | 99.423% | 6,203.1 | INR 2,987,131.00 | INR 4,588,597.80 | INR 108,843.00 | INR 7,684,571.80 |
| fixed_week_cover | 1029 | 0 | 95.938% | 4,868.6 | INR 2,927,107.60 | INR 3,601,433.52 | INR 766,857.00 | INR 7,295,398.12 |
| fixed_fortnight_cover | 540 | 0 | 74.611% | 3,495.2 | INR 1,824,943.80 | INR 2,585,480.13 | INR 4,792,599.00 | INR 9,203,022.93 |
| minmax_3_6 | 1091 | 0 | 100.000% | 4,756.7 | INR 3,079,130.20 | INR 3,518,640.10 | INR 0.00 | INR 6,597,770.30 |
| calendar_two_runs | 1115 | 25 | 99.979% | 5,163.8 | INR 3,190,829.60 | INR 3,819,772.91 | INR 3,990.00 | INR 7,014,592.51 |
| oracle_minmax | 1253 | 0 | 100.000% | 3,343.9 | INR 3,345,535.80 | INR 2,473,582.91 | INR 0.00 | INR 5,819,118.71 |

Capacity sweep on fixed_week_capacity: cadence held at one trip a week, machines resized.

| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|
| 2 | 5,000 | 1029 | 74.935% | INR 2,657,068.60 | INR 1,475,519.38 | INR 4,731,342.00 | INR 8,863,929.98 |
| 3 | 7,500 | 1029 | 94.691% | INR 2,915,226.80 | INR 3,043,852.80 | INR 1,002,057.00 | INR 6,961,136.60 |
| 4 | 10,000 | 1029 | 99.423% | INR 2,989,131.00 | INR 4,832,090.95 | INR 108,843.00 | INR 7,930,064.95 |
| 5 | 12,500 | 1029 | 99.943% | INR 3,010,663.80 | INR 6,655,010.85 | INR 10,815.00 | INR 9,676,489.65 |
| 6 | 15,000 | 1029 | 99.998% | INR 3,026,355.20 | INR 8,481,595.17 | INR 462.00 | INR 11,508,412.37 |

Capacity sweep on minmax_3_6: any day trips allowed, machines resized.

| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|
| 2 | 5,000 | 3195 | 100.000% | INR 6,666,632.80 | INR 2,193,951.57 | INR 0.00 | INR 8,860,584.37 |
| 3 | 7,500 | 1465 | 100.000% | INR 3,721,721.00 | INR 2,949,146.40 | INR 0.00 | INR 6,670,867.40 |
| 4 | 10,000 | 1079 | 100.000% | INR 3,056,951.80 | INR 3,553,913.93 | INR 0.00 | INR 6,610,865.73 |
| 5 | 12,500 | 973 | 100.000% | INR 2,871,950.00 | INR 3,882,770.03 | INR 0.00 | INR 6,754,720.03 |
| 6 | 15,000 | 939 | 100.000% | INR 2,797,718.40 | INR 3,918,001.84 | INR 0.00 | INR 6,715,720.24 |
