# auth-holds

An authorisation is a promise with a deadline. The deadline is set once, in days, for a whole
merchant book, and it decides two different losses at the same time.

## Problem

A card authorisation reserves money. The reservation expires after a window, and any settlement
that arrives after that window is refused: the merchant shipped or served the thing and the money
never lands. Extend the window and the opposite cost appears: abandoned holds keep customer
balances frozen for longer, and that money cannot be spent elsewhere.

Card systems pick one window for everything. A restaurant settles in a day or two with a tip on
top. A multi item order settles in pieces over a week. A hotel settles at checkout, up to two weeks
later, and usually for less than the deposit. A single number applied to all four is wrong for at
least three of them, and the error is invisible until settlement reports disagree with the ledger.

## Why it matters

In this book 30.5 percent of settlement value arrives after day 7. A 7 day window refuses USD
116,883.23 of USD 383,504.17, and every one of those refusals is work already delivered. The
merchant does not get a second authorisation for a shipped order: the customer has the goods, the
authorisation is gone, and the recovery path is an invoice nobody asked for.

The other side is not free either. Holding the whole book for 28 days recovers almost everything
and freezes customer money for 2.2 times as many dollar days as a 7 day window. The two costs are
counted in different units, which is exactly why teams pick one number and stop thinking about it.

## Design

One book, one hold ledger, two sweeps, one comparison.

The book: 2,500 synthetic authorisations over 170 days, USD 383,504.17 requested, in five merchant
classes. Restaurants authorise the pre-tip bill and capture the bill plus a tip of 8 to 26 percent.
Retail captures once within three days. Multi item orders capture in two to four pieces across
twelve days. Hotels authorise the stay plus 15 percent incidentals and capture a consumed amount at
checkout, 3 to 14 days later. A late batch class settles a full capture 8 to 25 days after
approval. Between 4 and 12 percent of each class never settles at all, which is where the frozen
funds come from.

The ledger stores every amount as integer cents and enforces one corridor: a capture may not exceed
the authorisation plus a tolerance in basis points. Two behaviours are modelled explicitly.
`refuse` rejects an over limit capture and leaves the whole ticket unsettled. `cap` settles what
fits and drops only the excess. That switch turns out to matter more than the tolerance itself.

The simulator processes one day at a time: it records the open hold stock at the start of the day,
then authorises new arrivals, then processes that day's captures, then expires holds whose window
closed at the end of the day. Expiry is inclusive of the final day, so a capture on the last legal
day still settles. Two numbers come out of every run: settled value, and frozen funds measured in
USD days, where one USD held for one day is one unit.

### Decisions and tradeoffs

| Decision | Why | What it costs |
|---|---|---|
| Two sided metric: settled value and frozen USD days | A window that only maximises capture always wins by being infinite | A dollar day weights every customer equally, with no balance or overdraft model |
| Integer cents with a basis point tolerance, rounded half up | Rounding must never be the reason a legitimate capture fails | The rounding convention is a choice, and a scheme that rounds down would differ by a cent per case |
| Expiry is the end of the final day | Batches land during the day, so a last day capture is legal | Every hold lasts one day longer than a midnight to midnight reading |
| A `refuse` and a `cap` mode for over limit captures | The two behaviours have very different costs and both exist in the wild | `refuse` assumes a single attempt, so its loss is an upper bound |
| Per class windows in the tiered policy | Multi item and hotel settlement lag is structural, not noise | The class table is an assumption, and one merchant can behave outside it |
| A seeded generator, with the book shuffled before numbering | No id can leak the capture schedule, and every run is byte identical | One book, so there is no sampling error bar |
| Hotels capture less than they authorise | Deposits and incidentals are the normal case, not an edge case | It makes frozen funds look larger, because the remainder sits until expiry |

## Run

```bash
# from the repo root
PYTHONPATH=artifacts/2026-11-19-auth-holds uv run python -m authholds.cli bench
uv run pytest artifacts/2026-11-19-auth-holds
```

The bench rewrites `results/summary.json` and `results/summary.md` in about a second. Standard
library only, no network, no clock reads, one seed.

## Results

Book: 2,500 authorisations, 2,967 settlement requests, USD 383,504.17 requested, USD 9,271.24 of
tips above the authorisation, 193 authorisations that never settle at all.

| Policy | Settled USD | Capture rate | Refused past expiry USD | Frozen funds USD days |
|---|---|---|---|---|
| blanket 7 days | 226,592.42 | 59.1% | 116,883.23 | 2,140,155.70 |
| blanket 14 days | 331,582.74 | 86.5% | 11,892.91 | 3,288,370.40 |
| blanket 21 days | 339,865.83 | 88.6% | 3,609.82 | 4,028,299.12 |
| tiered by class | 339,865.83 | 88.6% | 3,609.82 | 3,353,567.79 |
| ceiling, no expiry | 383,504.17 | 100.0% | 0.00 | 11,589,573.77 |

The window sweep, at a 15 percent tolerance and with over limit captures refused:

- 1 day: 20.2 percent captured, USD 285,559.66 refused.
- 3 days: 39.3 percent.
- 7 days: 59.1 percent, USD 116,883.23 refused.
- 14 days: 86.5 percent, USD 11,892.91 refused.
- 21 days: 88.6 percent.
- 28 days: 89.6 percent, with zero refusals past expiry.

Three things the numbers say.

**The default window is the loss.** Moving 7 to 14 days recovers USD 104,990.32 and settles 2,403
of the book's 2,967 settlement requests instead of 1,773, at the cost of USD 1,148,214.70 more
frozen funds days. Past 14 days the curve flattens: 14 to 28 days buys 3.1 points of capture for
another USD 1,427,368.30 in funds days. The settlement lag distribution, not the policy table, sets
that knee.

**Tiering buys the capture without the freeze.** The tiered policy applies 7 days to restaurants
and retail, 14 to multi item orders, and 21 to hotels and the late batch. It captures exactly what
a blanket 21 day window captures, 88.6 percent, and cuts frozen funds days by 16.75 percent
(USD 3,353,567.79 against USD 4,028,299.12). The extra window only has to cover the classes that
actually settle late.

**Refusing an over limit capture costs more than the tip it protects.** At a 7 day window and 15
percent tolerance, refusing the whole capture loses USD 40,028.52, which is 21.45 times the
USD 1,866.14 lost by settling only the amount that fits, and 4.32 times the entire tip book of
USD 9,271.24. The guard takes the authorised base down with the tip. A zero percent tolerance makes
the same point from the other side: it refuses USD 63,576.51, and a 5 percent tolerance reproduces
that figure exactly, because any tolerance below the smallest tip rate refuses every tipped capture
outright. That plateau is a property of the tolerance table, not a flat slope.

## Limits

- The book is synthetic and built to make the mechanism visible. It is not a sample of a real
  portfolio, and the level of the capture rate is a property of these assumptions.
- The 7 day window is a policy input, not a citation of any scheme rule. Real windows differ by
  scheme, merchant class, and transaction type, and a longer allowed window shifts every row.
- `refuse` models one attempt. A real merchant retries at the allowed amount and often recovers the
  base, so the refused column is an upper bound of the loss and `cap` is that retry compressed into
  one step.
- Frozen funds are counted in USD days, which is a liquidity proxy. A hold that pushes a customer
  into an overdraft costs more than its dollar days, and this model cannot see that.
- No chargebacks, no scheme fees, no partial capture rules beyond the tolerance, and no customer
  behaviour in response to a hold. Tips are modelled as an amount over the authorisation, not as a
  separate line a processor may treat differently.
- One seed, one book. Policy ordering is stable across the sweeps, but the size of each gap carries
  no error bar.

## Next

- Learn the per class window from observed settlement lag instead of assigning it, and compare the
  learned table against the hand set one out of sample.
- Add the cost of a refused capture on the customer side: a declined settlement is often re-presented
  as a new charge, which is where a second authorisation decline appears.
- Price the retry explicitly, with the decline fee and the delay, so `refuse` and `cap` are compared
  in money rather than in refusals.
