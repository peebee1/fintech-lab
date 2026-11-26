The charge code on an international payment does not change what the banks take. It
changes who pays.

I replayed 2,000 synthetic supplier invoices worth USD 12.1M through one, two and three
hop correspondent chains, under all three MT103 codes. The chains took USD 47,499.41,
which is 39.13 bps of the value, and no charge code changed that number by a cent.

SHA cost the payer 29.75 bps and left the supplier 39.13 bps short. OUR cost 61.20 bps
with nothing deducted. Both are true at once, which is the point: SHA looks 31.45 bps
cheaper on your ledger and is 7.68 bps more expensive in total. The difference is the
supplier's money and it never appears in your reconciliation.

The obvious repair, topping up the shortfall, is worse than doing nothing. The median
claim is USD 37 and the minimum wire fee is USD 35, so repairing every claim costs 92.72
bps against 61.20 for buying full delivery up front.

The free lever is the contract, not the code. Raising the tolerated deduction from USD
25 to USD 50 cut claims by 77 percent and total cost by 9.46 bps, with no supplier
concession, because those shortfalls were already being absorbed.

What I left out: the FX markup. On a real payment a 40 bps conversion spread is bigger
than every fee in this table, and it is the same under all three codes, so including it
would have hidden the thing I wanted to measure.

Code and numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-26-correspondent-fees
