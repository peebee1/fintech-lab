# The reserve is cheap, the hold is not, and the risk band is neither

A marketplace pays its sellers before the buyer's refund window closes. The seller
keeps the money, the refund arrives a month later, and the marketplace is the one who
has to find it. Two controls are supposed to cover that gap: hold the payout for a few
days, or hold a reserve back from every sale. They are priced differently and almost
nobody compares them on the same book.

This artifact does. It generates a synthetic seller book with sales, refunds on a lag
distribution, and sellers who quit, then replays eleven payout policies and a perfect
foresight floor. Every number below is produced by the committed code.

## Problem

On a T+1 payout, money leaves the day after the sale. Refunds in this book arrive
between 2 and 120 days after the sale, so every refund lands after the payout and
becomes a claim against a seller's future sales. If the seller is still selling,
the next payout can absorb it. If the seller has left, the marketplace eats it.

The usual answers are a hold (pay on day 7 or 14) or a reserve (pay 90 percent now,
release the rest after 30 days). Both reduce the loss. The question is what each one
costs, and the answer is not symmetric: a hold puts a capital charge on 100 percent of
sales, while a reserve puts it on 10 or 15 percent, for a similar amount of protection.

The second question is whether the risk band is worth its complexity. Most platforms
treat new and risky sellers differently, which sounds obviously correct. On this book
it is not, and the reason is measurable.

## Why it matters

On 400 sellers, 180 days, 52,349 orders and USD 6,927,844.81 of GMV, refunds cost
USD 254,124.66. Paying T+1 with no reserve writes off USD 57,605.04 of that, 22.7
percent of the refund book, and touches 263 of 400 sellers. A 15 percent reserve held
30 days cuts the write-off to USD 21,835.52 for USD 12,329.06 of float. A 14 day hold
on every seller writes off more, USD 33,537.86, and costs 2.6 times the float,
USD 31,813.71.

The difference is not a rounding error in the policy spreadsheet. It is the difference
between paying 50.2 bps of GMV for the refund problem and paying 86.4 bps, on the
number a marketplace finance team actually reports.

## Design

Five modules, one direction of data flow, money in integer cents.

- `payoutholds/book.py`: the book. 400 sellers in three observable bands, a join day, a
  tenure drawn from a band specific distribution, daily Poisson order counts, lognormal
  tickets, and refunds that fire with a band specific rate and a three part lag mixture
  (65 percent within 3 weeks, 25 percent to 60 days, 10 percent to 120 days).
- `payoutholds/policies.py`: eleven policies as pure terms, plus the two sweeps. A
  policy is a hold, a reserve rate, a reserve window, a clawback flag, and optionally a
  band split.
- `payoutholds/ledger.py`: the replay. Daily loop, refunds charged before the day's
  payout, held money consumed first, then clawback against later payouts, then the
  remainder written off. Every cent carries a sale day, so float is measured in
  dollar days and priced at 12 percent a year.
- `payoutholds/bench.py`: the ladder, the two sweeps, three seed books, the checks, and
  the committed output.
- `payoutholds/cli.py`: `bench` writes `results/`, `show` prints without writing.

| Decision | Why | Tradeoff |
|---|---|---|
| The book is drawn once, before any policy runs | Two policies must differ in payout terms, not in the orders they see | No policy can change seller behaviour, so a hold that drives churn is invisible here |
| A refund is charged to the seller's balance, fee included | A refund is the seller's money, and the admin fee is real | A platform that absorbs fees looks better than it should |
| Refunds land before the day's payout run | Money still held can cover them, which is the whole point of a reserve | Front-loading the refund gives the hold its best case |
| Clawback against later payouts is on by default | This is what makes a reserve work: the loss is small only where the seller keeps selling | A policy without clawback writes off 8.7 percent more |
| Funding is priced at 12 percent a year on every held cent | A capital charge is the honest common denominator between a hold and a reserve | The platform's actual borrowing cost may differ, and the ranking could move with it |
| The reserve is a fraction of each sale, not a fixed dollar floor | A floor would bind differently by seller size and confound the rate sweep | Small sellers are protected at a lower dollar amount |
| The risk band splits on tenure and band only | Both are observable at the time of the sale, so the policy is implementable | A band fitted on refund history would be in sample and is not modelled |
| The oracle holds exactly the refunds that arrive late | It gives a floor that no implementable policy can beat | It has perfect foresight, so it is a bound, not a plan |

## Run

```bash
cd artifacts/2026-11-27-payout-holds
PYTHONPATH=. uv run --project ../.. python -m payoutholds.cli bench   # writes results/
PYTHONPATH=. uv run --project ../.. python -m payoutholds.cli show    # prints without writing
```

Tests, from the lab root:

```bash
uv run pytest artifacts/2026-11-27-payout-holds
```

43 tests, deterministic, no network, no wall clock, no sleeps. Two identities are
asserted per seller: sales equal payouts plus money taken for refunds, and every refund
is covered from held funds, from later payouts, or written off. The two together pin
the cash in both directions.

## Results

Synthetic book, seed 20261127, 180 days, 400 sellers, 52,349 orders, USD 6,927,844.81
GMV, 1,932 refunds, USD 254,124.66 of refund cost, median refund USD 109.87. Funding at
12 percent a year.

| Policy | Hold | Reserve | Write-off | Float cost | Economic | Write-off bps | Economic bps | Sellers written off |
|---|---|---|---|---|---|---|---|---|
| pay_t1 | 1 | none | $57,605.04 | $2,260.84 | $59,865.88 | 83.15 | 86.41 | 263 |
| hold_7 | 7 | none | $45,062.09 | $15,880.07 | $60,942.16 | 65.04 | 87.97 | 231 |
| hold_14 | 14 | none | $33,537.86 | $31,813.71 | $65,351.57 | 48.41 | 94.33 | 189 |
| hold_21 | 21 | none | $24,979.60 | $47,726.18 | $72,705.78 | 36.06 | 104.95 | 156 |
| reserve_5 | 1 | 5.0% / 30d | $35,177.93 | $5,444.98 | $40,622.91 | 50.78 | 58.64 | 204 |
| reserve_10 | 1 | 10.0% / 30d | $25,911.97 | $8,879.54 | $34,791.51 | 37.40 | 50.22 | 166 |
| reserve_20 | 1 | 20.0% / 30d | $19,854.90 | $15,771.16 | $35,626.06 | 28.66 | 51.42 | 136 |
| hold_7_reserve_10 | 7 | 10.0% / 30d | $19,617.11 | $22,654.52 | $42,271.63 | 28.32 | 61.02 | 139 |
| reserve_10_no_clawback | 1 | 10.0% / 30d | $28,162.29 | $8,879.54 | $37,041.83 | 40.65 | 53.47 | 173 |
| tiered_hold | banded | banded | $28,282.07 | $29,323.46 | $57,605.53 | 40.82 | 83.15 | 155 |
| tiered_reserve | banded | banded | $29,260.88 | $19,420.24 | $48,681.12 | 42.24 | 70.27 | 165 |
| oracle | exact | exact | $0.00 | $8,226.01 | $8,226.01 | 0.00 | 11.87 | 0 |

### The hold loses on both counts

A 14 day hold writes off USD 33,537.86 and costs USD 31,813.71 of float. A 10 percent
reserve writes off less, USD 25,911.97, for USD 8,879.54. Strictly dominated: less
protection for more money. The hold sweep makes the mechanism plain. Economics against
paying T+1: 0 days USD 59,446.83, 3 days USD 60,522.98, 7 days USD 60,942.16, 14 days
USD 65,351.57, 21 days USD 72,705.78, 28 days USD 83,269.41. Even a three day hold is
worse in total than paying next day, because a hold taxes every sale while a refund is
3.7 percent of sales and only part of that fraction is a loss.

### The reserve has a knee at 15 percent

| From | To | Write-off saved | Float added | Net |
|---|---|---|---|---|
| 0% | 5% | $22,427.11 | $3,184.14 | $19,242.97 |
| 5% | 10% | $9,265.96 | $3,434.56 | $5,831.40 |
| 10% | 15% | $4,076.45 | $3,449.52 | $626.93 |
| 15% | 20% | $1,980.62 | $3,442.10 | $-1,461.48 |
| 20% | 25% | $1,024.56 | $3,433.47 | $-2,408.91 |
| 25% | 30% | $469.11 | $3,429.73 | $-2,960.62 |

The first five points save USD 22,427.11 of write-off for USD 3,184.14 of float. The
fifteen point to twenty point rung spends USD 3,442.10 to save USD 1,980.62. The write-
off keeps falling all the way to 30 percent (USD 18,361.23) but it never covers the
float again, and the residual is the set of sellers whose refund rate exceeds the
reserve or who leave before it is released.

### The risk band is the wrong shape

`tiered_hold` charges new and risky sellers 14 days plus a 10 percent reserve for 60
days and gives established sellers T+2. It cuts the write-off in half, to USD 28,282.07,
and costs USD 57,605.53 in total: USD 2,260.35 better than paying T+1, and USD 23,440.95
worse than the blunt 15 percent reserve. The banded reserve variant, 20 percent for 60
days on new and risky only, costs USD 48,681.12, USD 14,516.54 worse than the blunt
reserve.

The reason is in the band shares. Established sellers are 70 percent of the book and
89.7 percent of GMV, and they carry 61.6 percent of the T+1 write-off in dollars, at a
refund rate of 306 bps. New sellers run 526 bps and risky sellers 1,439 bps, but they
are 10.3 percent of GMV between them, so their higher rate produces 38.4 percent of the
loss. Exempting the established band gives up the protection that costs the most money
and saves the float that costs the least. A band is a bet that risk is concentrated by
rate; on this book it is concentrated by rate and diluted by volume.

### Three seeds, one ranking

| Seed | GMV | Pay T+1 write-off | Pay T+1 economic | Best flat | Best flat economic | Tiered hold economic | Oracle | Prize captured |
|---|---|---|---|---|---|---|---|---|
| 20261127 | $6,927,844.81 | $57,605.04 | $59,865.88 | reserve_15 | $34,164.58 | $57,605.53 | $8,226.01 | 49.8% |
| 20261128 | $6,878,626.82 | $56,675.93 | $58,921.37 | reserve_15 | $35,283.32 | $56,663.86 | $8,006.77 | 46.4% |
| 20261129 | $7,007,643.11 | $59,500.98 | $61,788.78 | reserve_15 | $38,856.73 | $58,367.52 | $8,458.65 | 43.0% |

The 15 percent rung wins on every book, and the best flat reserve captures 43.0 to 49.8
percent of the gap to perfect foresight. Half the prize is left on the table: the oracle
holds only the exact refunds that will arrive after payout, which no policy can know.

Clawback is worth naming separately. Turning it off at the same 10 percent reserve
raises the write-off from USD 25,911.97 to USD 28,162.29, so USD 2,250.32 of the
reserve's value is not the reserve at all: it is withholding the next payout.

## Limits

- Synthetic book, one generator, three seeds. The levels are the model's, not a
  market's. The ranking of reserve over hold is the claim, not the exact dollar.
- One refund per order, full or partial, and no second presentment. Real books have
  partial refunds, disputes and chargebacks with their own clocks, which would make the
  late tail longer and the hold look even worse.
- Fraud, KYC and account takeover are not modelled. Holds are often imposed for those
  reasons, and this artifact makes no claim about them. The claim is narrow: for refund
  risk alone, a hold does not pay.
- Clawback assumes the seller keeps selling. That is exactly why the residual exists,
  but a platform that cannot legally net against future payouts would look like the
  no-clawback row.
- Float is a capital charge at 12 percent a year on every held cent, charged to whoever
  holds it. It is not a cash transfer, and the platform's real cost of funds may differ.
- Reserve release is modelled as a fixed 30 days. A policy that releases early on good
  behaviour would sit between the flat reserve and the oracle.
- The band split is by tenure and band, never by observed refund history, so the policy
  is implementable but also coarse. A fitted band would score better in sample.
- The oracle is a bound with perfect foresight, not a plan.

## Next

- Price the reserve against a reserve that releases early for sellers with no claims in
  the window. That is the obvious implementable version of the oracle and would test
  whether the 49.8 percent capture is a policy limit or a design limit.
- Add a churn response to payout delay. Sellers who wait two weeks may leave, which
  would raise the true cost of the hold and strengthen the result rather than weaken
  it, but the size is unknown.
- Compare a rolling reserve balance (hold a target balance, release the excess) against
  the fixed percentage. The balance version should cut the float on high volume sellers
  without touching the protection.
