Every treasury report on this account said it was funded. It still could not pay at 11:00.

A card processor pays merchants before the acquirer settles the card sales that pay for them. In the book I built, the acquirer lands the early slice at 09:00, merchant payouts leave at 11:00 and 15:00, and the other 70 percent of the settlement arrives at 16:30. Over 720 business days, USD 1.37 billion of payouts, the cumulative net flow is USD 9,881. The account is, on every daily view, self funding.

393 of those 720 days are net positive. With no buffer, all 393 of them run short before the 11:00 batch. A positive daily net is not evidence that the account can pay.

So I priced the buffer nine ways. Holding nothing costs USD 448,355 a year in failed batches and facility charges. Sizing on the daily net at its 95th percentile holds USD 634,288 overnight and still misses a payout on 95.6 percent of days, at USD 271,703 a year, which is the textbook answer being expensive and wrong at the same time.

Sizing on the trailing distribution of the exact intraday requirement, at the 90th percentile, costs USD 106,970 a year with 84 failed batches and 12.7 percent of days shorted. A buffer of USD 1.61 million against USD 1.90 million of daily payouts, because the money that pays for today arrives after the last cutoff. The perfect forecast floor is USD 71,127, so 34 percent of what is left is information I do not have, not method.

The finding that matters is not the buffer. It is the schedule. Settling the same book at 08:00 instead of 16:30 drops the required float from USD 1,655,285 to USD 305,080 and the best policy from USD 106,970 to USD 33,638. Asked as a procurement question, an earlier settlement is worth about USD 73,000 a year to this book. No sizing policy gets close to that, because sizing pays for the problem and the schedule removes it.

Limit, said out loud: the book is synthetic. Every dollar is produced by committed code, but the volume and timing parameters are mine, and the claim I would defend is the ordering of the nine policies, not the absolute cost. The failure price is USD 250 a batch plus 10 bps, and a real failed payout also loses merchants, which would move the optimum right of the 90th percentile.

Code and the committed numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-18-intraday-liquidity
