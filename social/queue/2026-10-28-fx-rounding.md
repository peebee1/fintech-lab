One in five payout runs did not add up.

I built a small allocation engine for one payment split across several parties, in USD,
JPY and KWD, and measured four ways of rounding the split. Rounding each party's share
independently left 621 of 3,000 payouts off by one or two minor units (20.7%). Largest
remainder balanced all 3,000, and all 3,374 cases of an exhaustive sweep over every total
from 0 to 240.

Two things the numbers said that I did not expect.

First, the failure is not random. "Floor every share and give the leftover to the largest
party" is a two line loop, and it overpaid the biggest party on 95.7% of payouts, by as
much as 876 basis points of the payout. That is a quiet transfer to the largest seller in
the marketplace every single run.

Second, converting a payout pool once and then splitting it settles differently from
splitting it and converting each leg. Same inputs, both defensible, and they disagreed on
988 of 3,000 cross currency payouts (32.93%). Small, at most 2 minor units, but the
direction is roughly even, so it cannot be predicted or reconciled from the amount.

Limit, said out loud: everything here is synthetic. One seed, uniform random weights, and
rates I wrote into the benchmark as a snapshot. The percentages move if the weight
distribution moves, and a real marketplace has many small sellers and one dominant one,
which would make the largest party bias worse. The invariants do not move, which is why I
checked them exhaustively as well as by sample.

Code, tests and the committed results:

https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-10-28-fx-rounding
