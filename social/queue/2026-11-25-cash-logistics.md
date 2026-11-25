# An ATM is a stock, not a service

An ATM holds cash and sells withdrawals. The money sitting in it and the van that
refills it are one decision, and most networks answer it with a cadence.

On 60 synthetic machines over 120 days, 6,144,545 notes and INR 3,072,272,500
dispensed, the default pattern (one trip a week on a fixed weekday, filled to capacity)
cost INR 7,684,571.80 and still ran dry on 5,183 withdrawals. A min/max rule that may
send a van any day, triggers at three days of cover and fills to six, cost
INR 6,597,770.30 and served every withdrawal.

The default was not a tradeoff, it was dominated: it spent INR 1,069,957.70 more on
cash it did not need to hold to save INR 91,999.20 on trips, and was 0.577 points worse
on service.

The limit: a lost withdrawal is priced at the INR 21 interchange it forgoes, with no
churn and no support cost. That is why the cheapest rung of the capacity sweep is a
94.691% service level. In a real book that number is wrong, so service has to sit next
to cost, never under it.

Code, with the bench that reproduces every figure:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-25-cash-logistics
