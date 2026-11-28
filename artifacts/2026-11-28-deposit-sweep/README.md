# Deposit sweep: insuring the tail is free in yield, and costs thirteen links

A program bank holds customer money and places it at partner banks to earn interest.
Insurance is per customer per bank, capped at 250,000 dollars. A sweep engine that
optimises yield treats deposits as fungible: it fills the best paying bank first and
never asks whether a single customer now holds more than the cap there. That is the
default, and on this synthetic book it leaves 2.30 percent of deposits uninsured, all
of it sitting on ten customers.

The obvious repair is to cap every customer at 250,000 per bank and spread the excess.
The question is what that costs. On a 50.41 million dollar book it costs nothing in
yield, because the network's capacity, not the allocation rule, sets the blended rate.
It costs thirteen links, roughly 19.50 dollars a year in statements and tax forms.

The second question is whether the repair is worth doing badly. Splitting every customer
equally across all eight banks also reaches zero uninsured, using 5,088 links instead of
1,520. That is 5,352 dollars a year for the same protection.

## Problem

Deposits at a partner bank are insured up to 250,000 dollars per customer per bank. A
sweep engine has three inputs: each bank's rate, each bank's capacity, and each
customer's balance. It has one objective, interest income, and one operational bill,
the number of customer to bank links it maintains. Every link is a statement, a tax
form, and a reconciliation.

The default engine optimises the objective and ignores the cap. The result is invisible
in a yield report: the blended rate looks correct, capacity is used, and nothing on the
dashboard says that ten customers are holding 1.16 million dollars beyond insurance.

The tradeoff is not yield against safety. It is operating cost against who gets covered,
and the two are easy to conflate because both look like "spread the money around".

## Why it matters

On 1,500 synthetic customers and 50,410,003.08 dollars of deposits:

- The yield-only default leaves 1,162,238.27 dollars uninsured, 2.30 percent of the book,
  across 10 customers. Those ten hold 100 percent of the uninsured dollars.
- Capping every customer at 250,000 per bank, with at most three banks per customer,
  leaves 133,344.23 dollars uninsured, 0.26 percent, across 1 customer. Interest income
  and the blended rate do not move by one cent. The link count rises from 1,507 to 1,519.
- Four links reaches zero uninsured. Total cost: 13 extra links, 19.50 dollars a year.
- Splitting every balance equally across all eight banks also reaches zero. It uses
  5,088 links, 3.35 times as many as four links, and costs 5,352 dollars a year more.
- Serving the smallest balances first instead of the largest, at the same three link cap,
  raises uninsured deposits to 1,185,313.75 dollars across 11 customers, while saving
  1,800 dollars of link fees. Total interest is identical.

The last number is the one worth repeating. The allocation order does not change what
the program earns. It changes who is covered and who is paid the best rate.

## Design

Five modules, one direction of data flow, money in integer cents.

- `depositsweep/book.py`: the book. 1,500 customers from a two tier lognormal mixture,
  82 percent mass market around a 12,000 dollar median and 18 percent high balance around
  a 95,000 dollar median; eight partner banks with a rate and a hard capacity. Balances
  are drawn once, before any policy runs, so two policies differ in allocation and not
  in the book.
- `depositsweep/policies.py`: four policies as pure functions. `yield_only` fills banks
  in rate order and ignores the cap. `capped_k` fills each customer up to the cap in
  `k` banks at most, then sweeps the remainder into a bank it already holds or the next
  one with room. `even` splits each balance equally across all banks. `oracle` is
  `capped_k` with enough links for the largest balance.
- `depositsweep/bench.py`: measurement, the link sweep, the order sensitivity, the
  capacity test, the small book boundary, and twelve checks. Interest is truncated to
  cents per bank, so totals are integers and reproducible.
- `depositsweep/cli.py`: `bench` writes `results/`, `show` prints without writing.
- `tests/`: 42 tests, deterministic, no network, no wall clock, no sleeps.

| Decision | Why | Tradeoff |
|---|---|---|
| Money is integer cents, interest is truncated per bank | Two runs must produce the same bytes, and a float cent is a gate failure waiting to happen | Truncation costs a fraction of a cent per bank, which is not modelled as a payable amount |
| The insurance cap is 250,000 dollars per customer per bank, no joint accounts | This is the US deposit insurance rule that creates the constraint at all | Joint accounts double the cap, so this book is slightly harder to insure than a real one |
| Bank capacity is hard and given | Capacity is what actually rations the high rates in a program network | A real negotiation can raise or lower it, and the answer moves with it |
| Every cent is placed, including money that cannot be insured | Money does not evaporate when it stops being covered | The uninsured overflow pools at one bank, which flatters its balance sheet and ignores concentration risk beyond insurance |
| Uninsured overflow stays at a bank the customer already uses | Opening a new link to hold uninsured money breaks the link cap for no insurance gain | When that bank is also full, capacity forces a second link and the cap gives way |
| Link cost is a flat 1.50 dollars per customer per bank per year | Statements, a 1099-INT, and a reconciliation are per link and per year | Per bank minimums and onboarding costs are excluded, so the true bill is higher |
| Largest balance first is the default order | Spending scarce links on the customers who need them is the defensible rule | It is a choice, not a law: the smallest first variant is reported alongside |
| Interest is annual and simple, no rate moves | The claim is about allocation, not about the deposit beta or the rate path | A rate cut that moves balances would change the book under every policy |
| The oracle is `capped_k` with unlimited links | It isolates the link cap as the only difference between the policies | It is a bound on this network, not a plan a program can run |

## Run

```bash
cd artifacts/2026-11-28-deposit-sweep
PYTHONPATH=. uv run --project ../.. python -m depositsweep.cli bench   # writes results/
PYTHONPATH=. uv run --project ../.. python -m depositsweep.cli show    # prints without writing
```

Tests, from the lab root:

```bash
uv run pytest artifacts/2026-11-28-deposit-sweep
```

42 tests, gate green at 1,031 Python lines. The bench prints its own checks and exits 1 if
any fail, so a red table cannot be committed quietly.

## Results

Synthetic book, seed 20261128: 1,500 customers, 50,410,003.08 dollars, mean 33,606.66,
median 15,416.78, largest 883,344.23. The top 5 percent of customers hold 28.20 percent of
the book. Network capacity is 55,000,000 dollars, 109.10 percent of the book, with seven
of eight banks full and 91.65 percent of capacity used.

| Policy | Max links | Interest | Blended | Link cost | Links | Uninsured | Share | Exposed |
|---|---|---|---|---|---|---|---|---|
| yield_only | 1 | 1,910,440.10 | 3.78% | 2,260.50 | 1,507 | 1,162,238.27 | 2.30% | 10 |
| capped_1 | 1 | 1,910,440.10 | 3.78% | 2,260.50 | 1,507 | 1,162,238.27 | 2.30% | 10 |
| capped_3 | 3 | 1,910,440.10 | 3.78% | 2,278.50 | 1,519 | 133,344.23 | 0.26% | 1 |
| even | 8 | 1,910,440.10 | 3.78% | 7,632.00 | 5,088 | 0.00 | 0.00% | 0 |
| capped_12 | 12 | 1,910,440.10 | 3.78% | 2,280.00 | 1,520 | 0.00 | 0.00% | 0 |

Link sweep:

| Max links | Interest | Link cost | Links | Uninsured | Share | Exposed |
|---|---|---|---|---|---|---|
| 1 | 1,910,440.10 | 2,260.50 | 1,507 | 1,162,238.27 | 2.30% | 10 |
| 2 | 1,910,440.10 | 2,275.50 | 1,517 | 383,344.23 | 0.76% | 1 |
| 3 | 1,910,440.10 | 2,278.50 | 1,519 | 133,344.23 | 0.26% | 1 |
| 4 | 1,910,440.10 | 2,280.00 | 1,520 | 0.00 | 0.00% | 0 |
| 5 to 8 | 1,910,440.10 | 2,280.00 | 1,520 | 0.00 | 0.00% | 0 |

Dollars, all figures produced by `python -m depositsweep.cli bench`.

### The interest column is identical on purpose

Every policy fills the same seven banks to capacity in the same rate order, so bank
totals are the same and interest cannot differ. This is not a broken table and not a
control that failed to bind. It is the constraint: the book is 91.65 percent of network
capacity, and the top bank pays 4.55 percent whether the money there belongs to one
customer or twelve.

The capacity test makes it explicit. Doubling every bank's capacity raises income from
1,910,440.10 to 2,047,965.11, up 137,525.01, 7.20 percent of interest, 27 bps on the
book, with the blended rate moving from 3.78 to 4.06 percent. Capacity is worth paying
for. The insurance cap is not, in yield terms.

### The first rung is the default, not a repair

`capped_1` prints the same row as `yield_only`, and that is arithmetic rather than a
duplicate. With one link allowed, a customer that exceeds 250,000 has its excess swept
back into the bank it already holds, which is exactly what the cap blind engine does.
A one link cap is the floor of the ladder. Coverage starts moving at the second rung.

### The ladder is flat past four because nothing needs a fifth

The largest balance is 883,344.23, which needs four banks at 250,000 each. Past that, no
customer can use another link, so rungs five to eight are the same policy. The flat rungs
are reported rather than trimmed: the repeated rows are the finding, because the binding
constraint is the largest balance, not the link cap.

### Order decides who is covered, at zero cost to the program

Same three link cap, largest balance first versus smallest first:

| Order | Interest | Links | Link cost | Uninsured | Exposed | Top 10 interest |
|---|---|---|---|---|---|---|
| Largest first | 1,910,440.10 | 1,519 | 2,278.50 | 133,344.23 | 1 | 164,491.04 |
| Smallest first | 1,910,440.10 | 1,507 | 2,260.50 | 1,185,313.75 | 11 | 125,252.58 |

Interest is identical, to the cent. Uninsured dollars differ by 1,051,969.52, and the ten
largest customers earn 39,238.46 dollars less interest when the small balances are served
first, because the high rate banks are full by the time they arrive and the link cap
stops them reaching a fourth. "Largest first" is not a fairness claim. It is the only
order on this book that spends the cap on the balances that can exceed it.

### Where the invariance breaks

A book of 60 customers, 1,709,408.38 dollars, fits inside the top bank. There capacity
stops binding and the cap costs 242.32 dollars, 1.41 bps of yield: 77,778.08 at 60 links
under yield only, 77,535.76 at 61 links capped at three. Uninsured falls from 96,926.58
to zero. The invariance is a property of a full network, not of the cap.

## Limits

- Annual simple interest. No compounding, no accrued daily balance, no rate path.
- No joint accounts, so the cap is 250,000 for every customer. A joint account doubles it
  and makes the tail easier to cover.
- The link bill is flat at 1.50 dollars. Per bank minimums, onboarding, and per statement
  postage are excluded, so the operational cost is understated.
- Customer behaviour is fixed. Deposits do not move when a rate changes, there is no
  churn, and no deposit beta. A rate cut that shifts balances would reprice every policy.
- Capacities are hard and known in advance. Negotiating them is the actual job in a
  program, and it is outside this model.
- The uninsured overflow is placed at a bank the customer already holds, so the model
  ignores the balance sheet concentration that creates. It measures insurance only.
- The book is synthetic and seeded. The percentages are properties of this draw, not
  forecasts for a real program.
- Three links is an assumption about operations, not a measured constraint. The sweep
  reports every rung so a reader can pick their own.

## Next

- Add joint accounts with a doubled cap and an ownership share, the one common case that
  makes the tail materially cheaper to insure.
- Price per bank minimums and onboarding, which turn the flat link fee into a step cost
  and can make a bank uneconomic below some balance.
- Add the same day liquidity buffer: a sweep that places every cent leaves nothing for
  withdrawals, and the buffer is a real capacity haircut.
- Model deposit beta so a rate move changes the book, then check whether the allocation
  order still dominates the cap as the lever for coverage.
