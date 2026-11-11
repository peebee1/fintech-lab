More than half the money in a chargeback book needs no evidence at all. Most dispute teams never collect it, because they are tracking status and not clocks.

Every dispute runs on three deadlines at once. The issuer has a filing window counted from the transaction, and if it files late the case is procedurally invalid and you win it with zero documents. The merchant has a response window counted from the day the chargeback arrives, shorter for fraud codes than for service codes, and pushed forward when the deadline lands on a weekend. Then there is pre-arbitration, which only starts after you have already won, and forfeits money you had booked as recovered.

I built a simulator and a state machine for those clocks. 2,000 synthetic disputes, $356,862 disputed, $277,708 of it defensible, 40 analyst minutes a day, five policies on the same book.

A tracker with no clock at all, sweeping every case 25 days after it arrives, recovers 21.3%. It is not a bad team, it is a three week habit: 563 of its 804 forfeits are fraud claims, because 25 days is longer than a 20 day fraud window. It never wins a single fraud dispute.

With the real deadline per network and reason code, recovery goes to 66.5%. Add the two zero evidence checks, procedural and liability shifted, and it is 73.8%, because 621 cases carrying $153,411 need nothing but someone to file. Refuse to submit an evidence set that cannot win and precision goes from 0.45 to 0.94, though the money barely moves. Sort the queue by value per minute on the same analyst hours and it lands at 94.0%, $260,905, with 151 cases left unwon.

Unlimited analyst time only reaches 98.2%. The staffing constraint is worth $11,682. The queue ordering is worth $46,301.

Limit, said out loud: a complete evidence set wins with probability one in this model, and real representment wins about half the time on a complete set, because the issuer judges the document and not its existence. The windows are also illustrative, shaped like public network rules rather than a copy of one.

Code and the committed results:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-11-dispute-clock
