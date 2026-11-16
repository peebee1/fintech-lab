A confirmation count is a bet on the depth of the next reorg. It is priced in blocks and settled in dollars.

Every stablecoin processor picks one: 12 blocks, 30, 32, usually copied from a doc and applied to a USD 20 coffee and a USD 56,000 invoice alike.

I ran five of those rules over the same synthetic book. 4,000 payments a week across three chains, USD 1.67M of value a week, four held out weeks, so USD 6.69M scored per policy.

Crediting at inclusion lost USD 84,791.45, 136 basis points, on 366 payments. Twelve confirmations lost USD 13,912.83, and USD 13,857.15 of that was on the fast chain alone.

The part worth remembering is the shape. Going from 12 to 32 blocks, more than doubling the wait, only halved the loss. Going from 32 to 40 almost removed it. The step is where the number finally passes the depth of the incidents in that history, and nothing in the number tells you where that is.

A four row table by ticket size got the same book to USD 2,832.36, 4.6 basis points, with 92.5 percent of payments still clearing inside a minute. That was the cheapest change to make.

Limit, said out loud: the reorg process is synthetic and the rates are set high enough to produce signal in a week. A curve fitted to 28 days went to USD 202, then lost USD 6,740 when incidents forked 1.5x deeper than anything it had seen, worse than the four row table. A rule learned from history is a rule about history.

Code and the committed numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-16-finality-policy
