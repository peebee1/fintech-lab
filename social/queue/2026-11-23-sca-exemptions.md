# LinkedIn draft, 2026-11-23, sca-exemptions

The cheapest way to skip a payment challenge is not allowed. The gap between allowed and cheapest is the price of the rule.

In the EU, a remote card payment has to be strongly authenticated unless an exemption applies. The main one lets you skip authentication up to a threshold, and the threshold you may use depends on your fraud rate: EUR 100 at 13 basis points, EUR 250 at 6, EUR 500 at 1.

The part that gets missed: that fraud rate is measured over every remote card payment you process, authenticated or exempted. It is not per band. So every transaction you exempt adds fraud to the number that decides how much you may exempt.

I built a 60 day book of 49,752 remote card transactions and replayed seven policies over it, with the same fraud and abandonment draws for every one, so the comparison is not noise.

Challenging everything costs EUR 34,942.88. Almost all of it, 99.1 percent, is abandoned checkouts, not fraud.

Exempting everything costs EUR 4,710.16, all of it fraud, and it is over its own reference rate on 56 of 60 days. Thirty times over in the worst week.

The cheapest policy that never breaches costs EUR 25,026.14. It gives up EUR 20,315.98 against the unconstrained floor, and it still saves EUR 10,217.70 of friction for EUR 300.96 of added fraud.

Two things surprised me.

The risk test pays twice. At the same ceiling it can only remove exemptions, so it admits less fraud. Less fraud keeps the trailing rate down, and a lower rate keeps a higher ceiling unlocked. The screened policy ends up exempting more value than the unscreened one while losing a third of the fraud.

And the breach is a sensor problem, not a model problem. Fraud arrives with a reporting lag, so the policy that sits at the ceiling its trailing estimate allows spends the next few days above the rate that ceiling requires. Same policy, one rung lower: EUR 8,587.01 more, zero breach days.

The limit: the book is synthetic, the 7 day window and 2 day lag are my modelling choices rather than rule text, and the risk score is generated, so the cutoffs are not transferable. The shape of the finding is the point, not the euro totals.

Code, tests and the full table: https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-23-sca-exemptions
