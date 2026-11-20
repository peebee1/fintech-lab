# The card fee gap is a field, not a rate

A merchant negotiates basis points and then loses more than it won to transactions
that failed a qualification rule. This artifact prices that gap on a synthetic book,
partitions it by the rule that actually binds, and ranks the data fixes by what they
collect. Every number below is produced by the committed code.

## Problem

Card fees are not one rate. Each item is billed at a tier: qualified if the submission
carries the data the rate requires, downgraded if it does not. A commercial card sent
without its tax amount and customer code is billed at a higher tier than the same card
sent with them. A card not present transaction without an AVS or CVV result is billed
higher than one with them.

Merchants audit the rate. Almost nobody audits the qualification, because the statement
shows one line per tier and not the field that put the item there.

So the first question a merchant asks is "is my rate good", and the answer can be yes
while the bill is still 20% higher than the rate implies.

## Why it matters

On the book in `results/`, USD 11,174,093.62 of processed value was billed USD
255,120.61. The same transactions, fully qualified, cost USD 204,734.23. The difference
is USD 50,386.38, which is 45.09 basis points of processed value and 19.75% of the fee
bill.

Two things follow.

The gap is concentrated: one rule, a commercial card missing its Level 2 fields,
accounts for USD 29,420.29, or 58.4% of it, across 5,178 transactions. The fix is an
integration change, not a negotiation.

And the ranking is not the ranking a merchant expects, because a transaction can fail
several rules and is only billed at the highest one. Fixing a masked rule collects
nothing until the rule above it is fixed. Summing the per-rule rows overstates nothing,
but it does understate the gap: the seven single fixes add to USD 36,361.28, which is
USD 14,025.10 less than the gap, and that difference is exactly the value sitting behind
a higher failure.

## Design

Three modules, one direction of data flow.

- `qualification/card.py`: the rate card. Four card products, seven qualification
  rules, each with a basis point uplift and a fixed component. Fee is integer arithmetic,
  half up rounding, no floats on money.
- `qualification/book.py`: a synthetic merchant book. 61,985 transactions over 45 days,
  channel mix and product mix, a lognormal ticket with a commercial tail, and one
  probability per missing field that depends on the channel and the product. Fixed seed,
  fixed draw order.
- `qualification/audit.py`: the money. Billed fee, fully qualified fee, the gap, the
  partition by binding rule, and the recovery from every set of one, two or three fixes.

The engine's central object is a per transaction fee row: the fee at each of the eight
possible tiers. A fix set changes the tier to the first failure that is still open, so a
recovery is a lookup. A single fix is evaluated over the transactions that bind on it,
which is exact because no other transaction can move.

| Decision | Why | Tradeoff |
|---|---|---|
| One tier per item, the highest failing rule, not a sum of failures | That is how qualification tiers work: a transaction gets one tier, so precedence is the mechanism that makes repair order matter | A transaction marked at two failures only shows one in the partition. The `masked_cents` column prices the hidden one |
| Synthetic rate card with stated uplifts, no scheme document quoted | Keeps the artifact offline, deterministic and checkable, and every input is visible in one file | The dollar totals are a function of these inputs. A reader has to replace them with their own rate card to get their own number |
| Gap attributed to the binding rule | Gives an exact partition: the rows sum to the gap to the cent, which is a test | Attributes the whole gap to one cause even when a second failure is what makes the fix incomplete. Hence the two columns |
| Fast path that scans only transactions binding on a fixed rule | Makes 64 repair sets cost under a second on 62,000 transactions | Relies on precedence being monotone in uplift. Cross checked against a transaction by transaction recount in the tests |
| Rate cut modelled as flat basis points on billed value | One number, directly comparable to the data gap | A real renegotiation usually changes qualification tiers as well, so the comparison is conservative |
| 45 days with weekday volume factors, no holiday calendar | Enough shape to avoid a flat week, still deterministic | Cut off misses are understated, since a holiday calendar is where late batches actually come from |
| Effort as an ordinal 1 to 5 | Keeps the ranking honest about what is not measured | It is not hours or dollars, so the curve ranks recovery, not return on engineering time |

## Run

```bash
cd artifacts/2026-11-20-fee-qualification
PYTHONPATH=. uv run python -m qualification.cli bench    # writes results/
PYTHONPATH=. uv run python -m qualification.cli show     # prints without writing
```

Tests, from the lab root:

```bash
uv run pytest artifacts/2026-11-20-fee-qualification
```

The suite is deterministic: no network, no wall clock, no sleeps. It runs in about a
second and the gate runs it twice to catch nondeterminism.

## Results

Synthetic book, seed 20261120, 45 days, 61,985 transactions, USD 11,174,093.62 processed,
28,553 transactions with at least one qualification gap.

| Measure | Value |
|---|---|
| Billed | USD 255,120.61 |
| Fully qualified | USD 204,734.23 |
| Gap | USD 50,386.38 |
| Gap as share of processed value | 45.09 bps |
| Gap as share of the bill | 19.75% |

Gap by the rule that binds, with the part a single fix collects and the part left behind:

| Rule | Transactions | Gap USD | Share | Recovered alone | Left behind |
|---|---|---|---|---|---|
| unauthorized | 2,552 | 5,367.07 | 10.7% | 2,844.09 | 2,522.98 |
| commercial_data | 5,178 | 29,420.29 | 58.4% | 20,451.98 | 8,968.31 |
| mcc_mismatch | 2,108 | 1,943.35 | 3.9% | 1,445.90 | 497.45 |
| avs_cvv | 10,769 | 9,133.38 | 18.1% | 7,335.00 | 1,798.38 |
| commercial_l3 | 50 | 2,942.57 | 5.8% | 2,725.94 | 216.63 |
| stored_credential | 2,185 | 287.21 | 0.6% | 265.86 | 21.35 |
| late_batch | 5,711 | 1,292.51 | 2.6% | 1,292.51 | 0.00 |

The best repair set at each size:

| Fixes | Rules | Recovered USD | Share of gap | Marginal USD |
|---|---|---|---|---|
| 1 | commercial_data | 20,451.98 | 40.6% | 20,451.98 |
| 2 | commercial_data, avs_cvv | 30,485.41 | 60.5% | 10,033.43 |
| 3 | commercial_data, avs_cvv, commercial_l3 | 37,908.13 | 75.2% | 7,422.72 |
| 7 | all rules | 50,386.38 | 100.0% | 12,478.25 |

Against a negotiated rate on the same book:

| Cut | Saving USD | Share of the data gap |
|---|---|---|
| 5 bps | 5,588.58 | 11.1% |
| 10 bps | 11,174.24 | 22.2% |
| 25 bps | 27,934.77 | 55.4% |

The two best fixes recover 5.455 times what a 5 basis point cut is worth. The cut is
worth more than any single fix, which is the honest result: a 25 basis point cut is
still 55.4% of the gap. But the cut applies to every transaction and the fixes apply to
the ones that need them, and a cut has to be renegotiated while a fixed submission does
not.

The `late_batch` row is a structural check, not a coincidence: the lowest rule in the
order can never be masked, because any transaction that binds on it has no other
failure. Every rule above it has a non zero left behind column. That is precedence
working as specified.

`commercial_l3` is the other shape worth noting. Fifty transactions carry USD 2,942.57,
about USD 59 each, because the rule only fires on cards at or above USD 5,000. A ranking
by transaction count would put it last. A ranking by dollars puts it third.

## Limits

The rate card is synthetic. The uplifts and product base rates are inputs chosen to be
the right shape and magnitude, not quotations from a scheme document, and no real
merchant statement was used. The 19.75% share is a property of this book and these
probabilities. A reader who wants their number has to replace the card in
`qualification/card.py` and the gap rates in `qualification/book.py` with their own
statement and submission data.

The stress row repeats the whole analysis with every missing field probability at 0.4x,
on the same seed and the same volume. The gap falls to USD 23,674.48, 10.37% of the
bill, and the same pair still wins, at 66.3% of that smaller gap. So the ranking is not
an artifact of one parameter setting. It does not validate the levels.

The book is one merchant over 45 days. There is no holiday calendar, no month end batch
behaviour, no refunds or credits, and no per item cap or scheme fee on top of the
interchange component. Each of those would move the totals, and the cap would matter
most on small tickets, where the fixed component is already the larger part of the fee.

Effort units are ordinal. The curve says which fixes recover the most money, not which
fix is the best use of an engineering quarter.

Finally, a fix set is binary here: a rule is fixed for every transaction or none. A real
integration lands on a share of traffic, so the first month collects a fraction of these
numbers. See Next.

## Next

1. Replace the synthetic rate card with a real statement and rerun. The three commands
   do not change, only the inputs.
2. Model adoption: a fix applies to a share of transactions that ramps over the
   integration, so the recovery curve has a date attached instead of being one number.
3. Add the per item cap and the scheme fee so the fixed component is right, then check
   whether small ticket merchants get a different ranking.
4. Turn the masked column into a sequenced plan: fix the binding rule, then reprice what
   is left, then decide if the remaining tail is worth the integration.
