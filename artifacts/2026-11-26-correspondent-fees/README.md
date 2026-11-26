# The charge code is a cost allocation, not a cost

A cross-border payment carries one of three MT103 charge codes: OUR, SHA, or BEN.
The code decides who pays the bank charges, and nothing else. Most treasury
dashboards report the code's effect on their own ledger, which is the one place the
answer is least interesting.

This artifact replays 2,000 supplier invoices through synthetic correspondent chains,
applies each code in turn, and reports two ledgers side by side: what the payer spent,
and what the beneficiary received. Every number below is produced by the committed
code.

## Problem

A supplier invoices USD 4,200. Under SHA the payer's bank bills USD 10, two
correspondents take USD 18 and USD 12, and the receiving bank takes USD 9. The supplier
is credited USD 4,151 and the payer's bank statement shows a clean payment of USD 4,210.

Nobody in that chain is wrong. The payer chose SHA, which means the chain comes off
the amount. The question a treasury team actually asks is whether that is cheaper than
OUR, where one bundled charge delivers the full amount. On the payer's ledger SHA looks
31 basis points cheaper. In total it is not, and the difference is sitting in a
supplier's deduction claim folder.

The second question is what to do when a shortfall arrives. The obvious answer, send a
top-up payment, is priced by the same wire minimum that made the shortfall a problem:
on this book the median claim is USD 37 and the minimum wire fee is USD 35. Repairing a
small shortfall costs more than the shortfall.

## Why it matters

On the book in `results/`, 2,000 invoices worth USD 12,138,953 travel five corridors
over 90 days. The chains take USD 47,499.41, which is 39.13 basis points of the value
instructed.

| View | SHA everywhere | OUR everywhere | Difference |
|---|---|---|---|
| Payer's ledger | 29.75 bps | 61.20 bps | OUR costs the payer 31.45 bps more |
| Beneficiary shortfall | 39.13 bps | 0.00 bps | SHA moves it off the payer |
| Total economic cost | 68.88 bps | 61.20 bps | SHA costs USD 9,320 more in total |

The payer's ledger says SHA is cheaper by USD 38,180. The total says SHA is dearer by
USD 9,320. Both numbers are true, they just count different people's money. A team that
reports only the first is not lying, it is measuring its own P&L and calling it the
cost of payments.

The third line is the one that decides: the charge code is a contract term, and the
price of full delivery is 61.20 bps on this book.

## Design

Six modules, one direction of data flow, money in integer cents.

- `corrfee/book.py`: the corridors and the chains. Five routes with one, two and three
  hops, a lognormal ticket size with a USD 4,200 median, and a per hop deduction with
  its own floor and cap. The deduction is drawn once, before any policy runs.
- `corrfee/fees.py`: the tariffs. OUR is one bundled charge at 28 bps with a USD 35
  floor. The sender bank's own charge is 8 bps with a USD 10 floor. The second one is
  the same work under all three codes.
- `corrfee/policies.py`: nine policies as pure functions of the invoice. A policy
  chooses a code, and separately decides whether to top up a claim.
- `corrfee/settle.py`: the replay. One ledger row per invoice with the sender fee, the
  deductions, what arrived, the shortfall, and who carried it.
- `corrfee/bench.py`: the ladder, the two sweeps, the per corridor breakeven, and the
  numbers the README quotes.
- `corrfee/cli.py`: `bench` writes `results/`, `show` prints without writing.

| Decision | Why | Tradeoff |
|---|---|---|
| The chain's deduction is drawn once, for the whole book | Two policies must differ in who pays, not in what the chain takes | The model cannot answer "what if we routed around this hop", which is the next artifact |
| The sender bank's charge is identical under all three codes | It is the same work. SHA bills it on top, BEN deducts it, OUR bundles it, and that is the entire difference between them | A bank that genuinely discounts one code cannot be represented |
| OUR is one bundled price with no separate deduction | That is the product being bought: certainty | A flat bundle across corridors underprices three-hop routes, which is exactly why OUR wins UK-NG here |
| A shortfall below the contract tolerance is absorbed silently | This is why SHA survives in practice. Suppliers do not dispute USD 20 | The tolerance is the most consequential number in the model and the least standardised |
| A claim costs USD 18 whether it is paid or refused | Answering a query costs the same either way | An average across query types, and the source of the largest process cost here |
| A repair is a new OUR payment for the shortfall | That is what actually happens | Some banks waive fees on a recall, so the repair is priced at its worst |
| Economic cost is payer outlay plus beneficiary shortfall | A dollar moved is still a dollar spent | No churn or relationship penalty, which flatters SHA |
| The routing rules are fitted on this book | A corridor rule needs a deduction estimate before it has history | Both rules are in sample, and the README says so where it quotes them |

## Run

```bash
cd artifacts/2026-11-26-correspondent-fees
PYTHONPATH=. uv run python -m corrfee.cli bench    # writes results/
PYTHONPATH=. uv run python -m corrfee.cli show     # prints without writing
```

Tests, from the lab root:

```bash
uv run pytest artifacts/2026-11-26-correspondent-fees
```

46 tests, deterministic, no network, no wall clock, no sleeps. The suite runs in under
a second and the gate runs it twice to catch nondeterminism.

## Results

Synthetic book, seed 20261126, 90 days, 2,000 invoices, USD 12,138,953 instructed,
median ticket USD 4,200. Tariff: OUR at 28 bps, floor USD 35, cap USD 250. Sender bank
at 8 bps, floor USD 10, cap USD 60. A claim costs USD 18. The tolerance is the larger
of USD 25 and 5 bps.

| Policy | Claims | Repairs | Payer | Supplier | Total | Payer bps | Total bps |
|---|---|---|---|---|---|---|---|
| ben_all | 1,134 | 0 | $20,412.00 | $68,726.28 | $89,138.28 | 16.82 | 73.43 |
| sha_none | 827 | 0 | $36,112.87 | $47,499.41 | $83,612.28 | 29.75 | 68.88 |
| sha_claim_100 | 827 | 1 | $36,247.95 | $47,399.33 | $83,647.28 | 29.86 | 68.91 |
| sha_claim_50 | 827 | 189 | $54,437.96 | $35,789.32 | $90,227.28 | 44.85 | 74.33 |
| sha_repair_all | 827 | 827 | $99,309.59 | $13,247.69 | $112,557.28 | 81.81 | 92.72 |
| our_all | 0 | 0 | $74,291.68 | $0.00 | $74,291.68 | 61.20 | 61.20 |
| corridor_rule | 198 | 0 | $56,217.87 | $12,255.47 | $68,473.34 | 46.31 | 56.41 |
| cost_rule | 542 | 0 | $49,072.68 | $31,189.99 | $80,262.67 | 40.43 | 66.12 |
| oracle | 42 | 0 | $44,626.65 | $12,272.40 | $56,899.05 | 36.76 | 46.87 |

Read `ben_all` carefully. It is the cheapest row on the payer's ledger, by USD 15,701
against SHA, because it puts the sender bank's own fee on the supplier as well. That is
the whole reason BEN exists and the whole reason suppliers refuse it. The payer column
alone ranks BEN first and it is the second worst policy in the book.

### One row per corridor is worth more than any single code

| Corridor | Hops | Invoices | Value | Chain bps | SHA bps | OUR bps | Cheaper | OUR below |
|---|---|---|---|---|---|---|---|---|
| US-IN | 2 | 572 | $3,473,058.00 | 45.31 | 62.87 | 61.45 | OUR | USD 5,525 |
| EU-IN | 2 | 362 | $2,089,576.00 | 45.80 | 63.95 | 63.54 | OUR | USD 5,475 |
| US-MX | 1 | 414 | $2,524,949.00 | 25.83 | 43.29 | 61.10 | SHA | USD 9,700 |
| UK-NG | 3 | 250 | $1,562,641.00 | 63.59 | 80.74 | 60.02 | OUR | USD 3,950 |
| US-PH | 1 | 402 | $2,488,729.00 | 23.03 | 40.10 | 59.73 | SHA | USD 10,875 |

`OUR below` is the smallest invoice where the bundled charge undercuts the corridor's
expected SHA cost, found by walking the amount grid in `corrfee/bench.py`.

The two one-hop corridors are SHA below about USD 10,000 and OUR above it. The two-hop
corridors flip at about USD 5,500 and the three-hop corridor at USD 3,950. The reason is
structural: a chain deduction is capped per hop, so on a large ticket it shrinks as a
share of value, while the OUR bundle is priced at 28 bps and capped at USD 250. Large
tickets and long chains favour the bundle. Small tickets and short chains favour SHA.

`corridor_rule` takes the winner per corridor and costs USD 68,473.34, which is 4.79 bps
better than OUR everywhere and 12.47 bps better than SHA everywhere. That row is fitted
on this book and is reported as such.

### The top-up is the wrong repair

The obvious response to a deduction claim is to send the difference. It does not work,
and the reason is a floor, not a fee.

| Claim threshold | Repairs | Payer bps | Supplier bps | Total bps |
|---|---|---|---|---|
| USD 25.00 | 827 | 81.81 | 10.91 | 92.72 |
| USD 50.00 | 189 | 44.85 | 29.48 | 74.33 |
| USD 100.00 | 1 | 29.86 | 39.05 | 68.91 |
| USD 250.00 | 0 | 29.75 | 39.13 | 68.88 |
| never | 0 | 29.75 | 39.13 | 68.88 |

Every repair rung is worse in total than repairing nothing, and the top rung is the
worst. That is arithmetic: a top-up pays the shortfall, which the supplier was carrying
anyway, plus the wire fee plus the desk. The deadweight is the finding, and its size is
the surprise. The median claim is USD 37. A new OUR payment for USD 37 is charged at the
USD 35 floor, so repairing it costs USD 53 of overhead, the wire plus the desk, before
the USD 37 itself. Across all 827 claims the average total per repaired claim is USD
105.21, and USD 37 of that is money the supplier was owed.

Repairing every claim costs 92.72 bps against 61.20 for OUR everywhere, a difference of
31.52 bps, or USD 38,266. A team that promises suppliers full delivery and buys it by
top-up is paying 51 percent more than the bundle that delivers full delivery by default.

The sweep above also has a flat top: the largest claim in the book is USD 100.08, so
every threshold at or above it is the same policy. It is printed rather than trimmed,
because a reader who sees three identical rows should be able to check why.

### The contract tolerance is the lever, and it is nearly free

| Supplier tolerance | Claims | Claim share | Desk bps | Total bps |
|---|---|---|---|---|
| USD 0.00 | 1,672 | 83.60% | 24.793 | 81.41 |
| USD 10.00 | 1,672 | 83.60% | 24.793 | 81.41 |
| USD 25.00 | 827 | 41.35% | 12.263 | 68.88 |
| USD 50.00 | 189 | 9.45% | 2.803 | 59.42 |
| USD 100.00 | 1 | 0.05% | 0.015 | 56.63 |
| USD 250.00 | 0 | 0.00% | 0.000 | 56.62 |

Raising the tolerated deduction from USD 25 to USD 50 cuts the claim count by 77 percent
and the total cost by 9.46 bps, which is USD 11,483 on this book. It costs the supplier
nothing extra: the shortfalls were already being absorbed, the claims were paperwork on
top. The ceiling of this lever is the same number as the shortfall itself, which does not
move, so the tolerance is a pure admin lever until it starts to be worth disputing.

The first two rows are identical because the smallest lift any hop takes is USD 12. A
tolerance below the smallest deduction behaves as zero, so any contract term under
USD 12 is decoration.

### What a routing rule buys, and what it cannot

The oracle knows each invoice's chain before it chooses and costs USD 56,899.05, 46.87
bps. Against SHA everywhere it is worth USD 26,713.23. The two fitted rules recover:

- `corridor_rule`, one line per corridor: USD 68,473.34, 56.67 percent of that prize.
- `cost_rule`, expected chain bps against the actual bundle price: USD 80,262.67, 12.54
  percent. It is worse than plain SHA on the payer's ledger and worse than plain OUR in
  total. The expected value of the chain is the wrong statistic to route on: the rule
  buys OUR whenever the average says it is close, and gives up the cases where the
  chain happened to take nothing.

The remaining gap to the oracle, 9.54 bps, is the within-corridor variance that no rule
with a corridor mean can see. It is a price for information, not for a better rule.

## Limits

The book is synthetic and the tariff is modelled, not quoted. The floors, caps and
probabilities are chosen to be the right shape and magnitude for correspondent banking,
and the seed is fixed. Every level here is a property of this book.

FX is excluded on purpose. The conversion markup is charged by whichever party converts,
it is the same size under all three codes, and including it would add a large constant
to every row and hide the thing being measured. That is also the biggest omission: on a
real payment, a 40 bps FX markup is larger than every fee in this table.

OUR is priced as one flat bundle. A real bank prices OUR by corridor, and a three-hop
route to a thin currency costs more than a two-hop route to a deep one. The flat bundle
is why OUR wins UK-NG by 20 bps here, and that number should be read as an upper bound
on the bundle's advantage.

The tolerance is treated as a contract term that a supplier has signed. At USD 250 the
model produces 56.62 bps, which no supplier would accept. The sweep is there to show the
shape of the lever, not to recommend the top rung.

No relationship cost, no churn, no late delivery penalty. A supplier that absorbs USD 39
bps of deductions either prices it back into the next invoice or leaves, and neither is
in this model. This is the largest understatement and it runs in SHA's favour.

Every shortfall above tolerance is assumed to become a claim. In practice suppliers
batch them, chase quarterly, or write them off, which would lower the desk cost and make
SHA look better.

Payments are one way. There is no recall, no reject and no return, so the second
conversion that a failed payment triggers is not modelled.

Both routing rules are fitted in sample. `corridor_rule` uses each corridor's realised
deduction, which is knowledge a real treasury would have after a quarter, not before it.

## Next

1. Add the FX markup and re-run the ladder. The prediction is that the charge code
   debate shrinks to a rounding error next to the rate.
2. Model the return path: a beneficiary bank that rejects a short-paid invoice sends it
   back, which costs a second conversion and a second fee. That is the failure SHA
   actually produces.
3. Split the book into two months, fit the corridor rule on the first and score it on
   the second. The 56.67 percent capture is in sample and should fall.
4. Price OUR per corridor instead of flat, and find out how much of the UK-NG result
   survives.
5. Add a negotiation view: given a supplier that will accept a stated tolerance, what is
   the cheapest pair of code and tolerance, and who pays for it.
