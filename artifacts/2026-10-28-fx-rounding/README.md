# Money that does not add up

An allocation engine for one payment split across several parties, in currencies whose
minor unit is not a cent, with the FX rounding order treated as a decision rather than
an accident.

The claim: per share rounding does not fail loudly, it fails by one or two minor units,
in a pattern that is systematic enough to measure. Over 3,000 synthetic payouts, 621 of
them (20.7%) did not add back to the amount that was collected. Largest remainder
balanced all 3,000, and all 3,374 cases of an exhaustive small total sweep.

## Problem

Take 100.00 USD and split it three ways.

- Largest remainder: 33.34, 33.33, 33.33. Adds to 100.00.
- Round each share to the nearest cent and ship it: 33.33, 33.33, 33.33. Adds to 99.99.

The cent did not vanish. It is in a suspense account, or on a dashboard that nobody
reconciles, or in a support ticket six weeks later. The second method is not a typo: it
is what `round(share, 2)` does in every language, applied per party, which is the
obvious implementation when the amount is small and the parties are few.

The same question appears one level up in cross currency payouts. A EUR pool paid out to
sellers held in USD, JPY and KWD can be converted once and then split, or split and then
converted leg by leg. Both orders are defensible. They disagree on a third of payouts,
because each leg rounds separately and the errors do not cancel.

## Why it matters

Three reasons, in order of how much they cost.

1. **It breaks the ledger invariant that everything else trusts.** A payout run that
   books one total and pays out a different sum is an unreconciled settlement line. Every
   downstream report built on it (revenue recognition, tax withholding, PSP settlement,
   partner statements) inherits the gap, and none of them can tell you where it came from.
2. **The error is biased, not random.** Independent rounding looks like noise that should
   cancel. In a sample it mostly does, and in one common implementation it does not:
   floor every share and give the leftover to the biggest party overpays that party on
   95.7% of payouts, by up to 876 basis points of the payout in the worst case. That is a
   quiet transfer of value to the largest seller in the marketplace, every run.
3. **"Cents" is a US assumption.** JPY has no minor unit, KWD has three. An engine that
   scales by 100 is wrong for both, and the failure is a factor of ten or a hundred, not
   a rounding unit.

## Design

Five small modules, each with one job, no floats anywhere on the money path.

- `fxalloc/money.py`: `Money(currency, minor)` plus the ISO 4217 exponent table (USD 2,
  EUR 2, GBP 2, JPY 0, KWD 3). Parsing refuses more precision than the currency has
  instead of rounding silently, and arithmetic refuses to mix currencies.
- `fxalloc/rounding.py`: `half_up`, `half_even`, `truncate`, each taking a `Fraction` and
  returning an `int`. Sign handled by rounding the magnitude, so a refund rounds like the
  charge it reverses.
- `fxalloc/alloc.py`: exact shares as `Fraction`, then four strategies: `largest_remainder`,
  `floor_to_largest`, `naive_half_up`, `naive_half_even`. `reconcile()` returns the
  residual and, separately, the same gap recomputed from exact shares.
- `fxalloc/fx.py`: rates parsed as exact rationals from decimal strings, conversion that
  respects both currencies' exponents, and the two orderings (`convert_then_split`,
  `split_then_convert`) side by side so the disagreement can be counted.
- `fxalloc/bench.py`: the four experiments. Pure functions, one seed, no clock, no network.

### Decisions and tradeoffs

| Decision | Alternative | Why this one |
|---|---|---|
| Integer minor units | `Decimal` major units | The exponent becomes an explicit parameter instead of a `quantize` call somebody forgets on the JPY path |
| Largest remainder as the default | Floor then give the leftover to the largest | Both balance; only one keeps every party within one minor unit of its exact share. The measured cost of the other is in the bias table below |
| Round the magnitude, restore the sign | `floor(x + 1/2)` on the signed value | On negatives the naive form rounds toward positive infinity, so refunds do not mirror charges |
| Rates as `Fraction` from a decimal string | `float`, or `Decimal` with a context | A rate is a quote with a finite decimal expansion. Exactness before the rounding decision is the point, not float being wrong today |
| Both FX orderings implemented | Pick one and document it | The disagreement is the finding. A payout system has to know which order its downstream consumers assume |
| `reconcile()` returns two numbers | A single `residual` | Residual and the gap explained by per party errors are computed independently and asserted equal. A sign convention flip passes `residual == 0` on clean data and only surfaces on mixed sign cases |
| Bias in basis points | Summed minor units | Adding a JPY yen to a KWD fils is an FX rate nobody stated, which is the mistake this artifact is about |
| Refunds by sign symmetry | A separate refund allocator | One code path, tested in both directions, instead of two that drift apart |

## Run

From the repository root:

```
PYTHONPATH=artifacts/2026-10-28-fx-rounding uv run python -m fxalloc.cli bench
```

That prints every table below and rewrites `results/` (five JSON files and `summary.md`).
Under a second, no network, no keys.

One allocation under every method, 100.00 USD split three ways:

```
PYTHONPATH=artifacts/2026-10-28-fx-rounding uv run python -m fxalloc.cli split 10000 USD 1 1 1
```

Tests:

```
uv run pytest artifacts/2026-10-28-fx-rounding
```

83 tests, deterministic, no clock and no network. One test regenerates `results/` into a
temporary directory and compares it to the committed files, so the numbers in this README
cannot drift from the code that produced them.

## Results

Synthetic payouts: seed 20261028, 3,000 runs, 2 to 5 parties, weights 1 to 1,000 with an
8% chance of a zero weight party, totals 1 to 250,000 minor units, currencies USD, JPY
and KWD.

### Does the payout add up

| Method | Unbalanced | Rate | Overpaid | Underpaid | Worst gap (minor) |
|---|---|---|---|---|---|
| largest_remainder | 0 | 0.0% | 0 | 0 | 0 |
| floor_to_largest | 0 | 0.0% | 0 | 0 | 0 |
| naive_half_up | 621 | 20.7% | 317 | 304 | 2 |
| naive_half_even | 622 | 20.73% | 315 | 307 | 2 |

By currency, for the method that fails:

| Currency | Minor digits | naive_half_up unbalanced | largest_remainder unbalanced |
|---|---|---|---|
| USD | 2 | 19.63% | 0.0% |
| JPY | 0 | 22.43% | 0.0% |
| KWD | 3 | 20.02% | 0.0% |

The failure rate is roughly one in five regardless of the exponent. What changes with the
currency is the size of the miss relative to the payout: one yen out of a 300 yen payout
is 33 basis points, one fils out of 30,000 is 0.3.

### Who gets the benefit

A separate draw of 3,000 payouts. Excess is the largest party's allocation minus that
party's exact share, in basis points of the payout.

| Method | Largest party overpaid | Rate | Mean excess (bps) | Worst excess (bps) | Worst excess (minor) |
|---|---|---|---|---|---|
| largest_remainder | 1413 | 47.1% | -0.01 | 38.2 | 0.757019 |
| floor_to_largest | 2871 | 95.7% | 0.84 | 876.57 | 3.299138 |
| naive_half_up | 1399 | 46.63% | 0.01 | 38.2 | 0.5 |
| naive_half_even | 1394 | 46.47% | 0.01 | 38.2 | 0.5 |

Largest remainder is not generous to the biggest party: mean excess -0.01 basis points,
which is noise around zero, and the worst case stays under one minor unit. Floor then
give the leftover to the largest is generous on 95.7% of payouts, and in the worst case
hands the largest party 8.76% more than its exact share.

### Does the conversion order change the settlement

EUR source, 3,000 payouts, exact decimal rates (synthetic snapshot, see Limits).

| Target | Payouts | Disagreed | Rate | Over | Under | Worst gap (minor) |
|---|---|---|---|---|---|---|
| USD | 1007 | 338 | 33.57% | 174 | 164 | 2 |
| JPY | 997 | 324 | 32.5% | 158 | 166 | 2 |
| KWD | 996 | 326 | 32.73% | 160 | 166 | 2 |

988 of 3,000 payouts (32.93%) settle to a different number depending on which of the two
orders the system used. The size is small, at most 2 minor units here, and the direction
is close to even, so this is not a bias. It is worse than a bias in one specific way: it
cannot be predicted from the payout amount, so a reconciliation break appears on a third
of runs and disappears on the next one when the amounts change.

### Exhaustive invariants

3,374 cases: every total from 0 to 240 against 14 weight families (equal splits of 2 to 5
parties, uneven splits, zero weight parties, a 999:1 split).

| Check | Violations |
|---|---|
| largest_remainder preserves the total | 0 |
| per party deviation under one minor unit | 0 |
| residual equals explained gap | 0 |
| zero weight party receives nothing | 0 |
| naive_half_up loses the total | 1571 (46.56% of cases) |

Nearly half of the smallest cases break under per share rounding, because at small totals
one minor unit is a large fraction of the payout. That is not a toy result: tips, fee
splits and per item allocations are exactly these sizes.

### The worked example

100.00 USD, weights 1:1:1.

| Method | Parts | Sum | Residual |
|---|---|---|---|
| largest_remainder | (3334, 3333, 3333) | 10000 | 0 |
| floor_to_largest | (3334, 3333, 3333) | 10000 | 0 |
| naive_half_up | (3333, 3333, 3333) | 9999 | 1 |
| naive_half_even | (3333, 3333, 3333) | 9999 | 1 |

## Limits

- Every payout is synthetic and comes from one seed. Change the weights, the party
  count or the total range and the percentages move. The invariants do not move, which is
  the point of checking them exhaustively as well as by sample.
- The weight distribution is uniform random, not a real marketplace. Live marketplaces
  are closer to a power law with many small sellers and one dominant one, which would
  make the largest party bias worse and the per payout miss smaller relative to totals.
- The FX rates are a synthetic snapshot written into `bench.py`. They are not a live
  quote, not a mid market rate, and not advice. Nothing here models spread, fees, or the
  rate a PSP would actually apply.
- One conversion hop only. A payout routed through two currencies has two rounding
  events, and this artifact does not measure how they compound.
- Only allocation of a positive total is benchmarked. Refund allocation is sign symmetric
  and tested, not measured.
- "Fair" here means one specific thing: every party within one minor unit of its exact
  share, and the total preserved. Actual fairness between parties under a given rounding
  rule over many payouts is a different question, not answered here.
- No rail behaviour. Some schemes round fees up to the next minor unit, some require the
  fee to be charged separately, and none of that is modelled.

## Next

1. Add a two hop conversion chain and measure whether the drift compounds linearly or
   cancels, because that decides whether a per hop correction is enough.
2. Replace the uniform weights with a power law and re-run the bias table, to see how far
   the 876 basis point worst case grows with a dominant party.
3. Model per rail rounding rules (fees rounded up, minimum unit caps) as a table, the way
   the mandate simulator treats rail parameters.
4. Package `reconcile()` as a guard that runs over a settlement feed and fails the run
   before money moves, with the residual and the explained gap both reported.
