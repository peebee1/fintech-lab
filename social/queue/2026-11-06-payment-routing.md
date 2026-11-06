The cheapest payment provider cost 4 percent of net margin.

I built a routing bench: 50,000 synthetic transactions, three acquirers, hidden approval curves by card type, region and ticket size. Route on the lowest published fee and you pay 124.4 basis points, capture 88.9 percent of transactions and keep $38,271 per 1,000. Route on expected net margin and you pay 151.3 basis points, capture 94.3 percent and keep $39,802.

Twenty-seven extra basis points buys five points of authorization, and that trade is worth about four times what it costs. Fee-only routing was the worst of the three choices in 7 of the 12 segments. The worst case is cross-border large tickets, 25 dollars per transaction behind.

The part I did not expect: the learned routing barely beat a three-line rule table. Three rules written from vendor decks recovered 4.06 percent. Thompson sampling landed 0.06 percent below the full-knowledge reference, epsilon greedy 0.9 percent below it. If your segments are stable and you know them, a table is enough, and I would rather have the table I can read.

What a table cannot do is notice a change. I moved one provider's debit approval down mid-stream. The rules lost 0.9 percent against full knowledge and kept routing there. The all-history Bayesian posterior lost 1.25 percent, because after 25,000 transactions it was too sure to see the shift. A version that keeps only the last 300 attempts per segment stayed level, and sat 1.8 percent below the all-history version before the shift. Adaptation is a setting with a price, not a property of AI routing.

Limit, said out loud: the book, the fee schedules and the approval curves are synthetic, and I wrote all three after I knew which provider was strong where. Treat the shape of the result as the claim, not the dollar figure.

Code and the committed tables:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-06-payment-routing
