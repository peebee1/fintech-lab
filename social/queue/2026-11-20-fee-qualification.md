# LinkedIn draft, 2026-11-20, fee-qualification

Your card rate is not the reason your card bill is high. A field you did not send is.

A merchant negotiates basis points, then submits transactions that fail a qualification rule and pays a higher tier for them. The statement shows the tier, not the field that put the item there, so the person who negotiates the rate and the person who owns the integration never compare notes.

I priced both on the same book: 61,985 transactions, USD 11,174,093.62 of processed value. The bill was USD 255,120.61. The same transactions, fully qualified, cost USD 204,734.23. The gap is USD 50,386.38, which is 19.75 percent of the bill, and one rule carried 58.4 percent of it: commercial cards sent without tax amount and customer code.

Two things I did not expect.

The fixes are not additive. A transaction is billed at the worst rule it fails, so fixing a masked rule collects nothing until the rule above it is fixed. The seven single fixes add to USD 36,361.28, which is USD 14,025.10 short of the gap, and that shortfall is exactly the money sitting behind a higher failure.

And the ranking by dollars is not the ranking by count. Missing Level 3 line items hits 50 transactions and carries USD 2,942.57, about USD 59 each, because the rule only fires above USD 5,000. A queue sorted by volume would never touch it.

The two best fixes recover USD 30,485.41, which is 5.455 times what a 5 basis point rate cut is worth on the same book. A 25 basis point cut would still beat the pair, so this is not data over negotiation. It is that most teams only run one of the two, and the cheaper one is usually the one nobody owns.

The limit: the rate card is synthetic, shaped like published card pricing but not quoted from a scheme document, and every missing field probability is an input. The ranking survived cutting those probabilities to 0.4x; the dollar totals are this book's, not yours.

Code, tests and the full table: https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-20-fee-qualification
