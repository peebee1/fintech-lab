# LinkedIn draft, 2026-11-19, auth-holds

A card authorisation has an expiry date, and the date you pick loses money either way.

Pick short and settlements arrive after the window closes. Pick long and customer balances stay frozen on holds nobody will ever capture. Card systems pick one number for the whole book, which means the number is wrong for most merchants in it.

I built a hold ledger and a synthetic merchant book to put both costs in the same table. 2,500 authorisations, USD 383,504.17 of settlement value. At a 7 day window, 30.5 percent of that value arrived too late and USD 116,883.23 was refused. Holding everything 21 days recovered 88.6 percent, and froze customer funds for 2.1 times as many dollar days.

The two results worth keeping:

Matching the window to the merchant class captured the same 88.6 percent as a blanket 21 day window, with 16.75 percent fewer frozen funds days. The extra window only needs to cover the classes that actually settle late.

Refusing an over limit capture cost USD 40,028.52. Settling only the amount that fit cost USD 1,866.14. That gap is 4.32 times the entire tip book, because the refusal takes the authorised base down with the tip. The guard was bigger than the thing it was guarding.

The limit: this is a synthetic book with one seed, and the 7 day window is a policy input, not a citation of any scheme rule. Read it as a model of the tradeoff, not a benchmark of a real portfolio.

Code, tests and the sweep table: https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-19-auth-holds
