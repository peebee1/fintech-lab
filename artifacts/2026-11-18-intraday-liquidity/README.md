# Size the buffer at 11:00, not at midnight

A card processor funds merchant payouts before the acquirer settles the card
sales that pay for them. The account looks flush on every daily report and still
needs USD 1.6M in it before the first payout batch leaves. This artifact prices
that gap, and measures what a timing aware buffer saves against the textbook one.

Everything here is synthetic. No real account, merchant, acquirer, or balance
appears in this artifact.

## Problem

The operating account of a card acquirer sees four movements a day:

- 09:00 the acquirer settles the early slice of yesterday's card sales
- 11:00 merchant payout batch one leaves
- 15:00 merchant payout batch two leaves
- 16:30 the acquirer settles the late slice of yesterday's card sales

So 70 percent of the money that pays for today's payouts lands 90 minutes after
the last payout cutoff. Treasury has to set one number each evening: the opening
balance for tomorrow. Anything above it gets swept, anything below it has to be
covered by an intraday facility at a price, and a payout that cannot be funded
leaves late.

The daily view of this account is uninformative. Over 720 business days the book
below has a cumulative net flow of USD 9,881 on USD 1.37 billion of payouts, and
393 of the 720 days are net positive. A treasury model that sizes the buffer from
the daily net position concludes that this account needs almost nothing.

## Why it matters

Failed or late merchant payouts are the loudest failure a payments company has.
They cost an SLA credit, a support ticket per merchant, and sometimes the
merchant. The buffer that prevents them is real money on the balance sheet every
single night, priced at the cost of capital.

Both numbers are large, and the usual answer (hold the worst net outflow seen in
the last month) is wrong in an expensive direction. The interesting question is
not whether to hold a buffer but which quantity to take a percentile of. Take it
of the daily net and you hold the wrong number. Take it of the largest single
payout batch and you are closer. Take it of the worst intraday cumulative deficit
and you are at the answer: 24 percent cheaper than the gross batch rule, and
still missing on 13 percent of days.

## Design

Four modules, all pure functions of a seed, no clock and no network:

| Module | What it does |
|---|---|
| `liquidity/book.py` | Generates the float book: card volume, settlement split, payout batches, slip days, spikes |
| `liquidity/sim.py` | Walks a day event by event against an opening balance, counts failed batches and the uncovered gap, prices the day |
| `liquidity/policy.py` | Nine policies, each one returning the opening balance for tomorrow from history only, plus an oracle bound |
| `liquidity/bench.py` | Walk forward evaluation, sweep, regimes, fee sensitivity, writes `results/` |

The central quantity is `required_opening(day)`: the smallest opening balance that
funds every payout at its scheduled minute. It is computed by walking the day in
time order and taking the worst cumulative deficit at a payout instant. That
number is the ground truth. A test asserts the invariant that makes it exact:
funding a day at `required_opening` produces zero failed batches, and funding it
one cent lower produces at least one. The buffer policies are estimators of that
quantity, and the evaluation measures how well each estimator does on days it has
never seen.

| Decision | Choice | Tradeoff |
|---|---|---|
| Buffer is per day, not cumulative | Treasury sweeps the surplus and funds the shortfall overnight, so each day starts at the chosen opening balance | Removes the compounding balance path, which would let one bad week dominate three years of results, and matches how an operating account is actually run |
| Net flow is break even, not profitable | Settlement and payout ratios picked so the book nets USD 9,881 over 720 days | Makes the daily view maximally misleading, which is the point, but it understates the buffer a growing book needs |
| Ground truth is the intraday deficit, not a simulated failure | `required_opening` is exact by construction, and the "one cent less" invariant is tested | The model cannot score forecast error separately from policy error |
| Failure cost is a fee plus a facility charge | USD 250 per failed batch plus 10 bps on the uncovered gap | A flat fee per batch is what the SLA actually charges, but a real incident has a tail (lost merchants) this does not price |
| Money is integer cents | Every amount is an int | Rounding the facility charge per day is visible at small gaps; at these amounts it is immaterial |
| Quantiles are nearest rank on the trailing window | No interpolation, no numpy | A 40 day window cannot resolve a 99th percentile, so the top rung is named `peak_p100` and is exactly the trailing maximum |
| Walk forward with 60 days of burn in | A policy sizing day i sees days 0 to i-1 only, and the first 60 days are never scored | Costs 60 of 720 days, and no result here can be a fit to its own answer |

Cost per day is `opening x 2.18 bps` for the float (5.5 percent a year over 252
business days), plus USD 250 per failed batch, plus 10 bps on the uncovered
amount. Annualized at 252 divided by the 660 scored days.

## Run

```bash
cd artifacts/2026-11-18-intraday-liquidity
PYTHONPATH=. uv run python -m liquidity.cli bench      # rewrites results/
PYTHONPATH=. uv run python -m liquidity.cli show       # prints the committed ladder
uv run pytest artifacts/2026-11-18-intraday-liquidity  # 37 tests, about 1 second
```

Stdlib only. Needs `python3` and nothing else. The bench runs in under a second.

## Results

Book: 720 business days, USD 1,369,861,695 of merchant payouts, mean USD 1,902,586
a day, cumulative net flow USD 9,881, 393 net positive days, 27 days where a
slipped settlement arrived the next morning instead of at 16:30.

The requirement, over the 660 scored days:

| Statistic | Required opening USD |
|---|---|
| mean | 1,294,716 |
| p50 | 1,270,039 |
| p90 | 1,655,285 |
| p95 | 1,789,709 |
| p99 | 2,709,818 |
| worst day | 3,079,874 |

That is 68 percent of a day's payouts held overnight on an average day, because
the settlement that pays for it arrives after the last cutoff.

Annual cost by policy, 660 scored days annualized at 252:

| Policy | Mean opening USD | Annual cost USD | Carry | Fees | Facility | Failed batches | Days shorted |
|---|---|---|---|---|---|---|---|
| zero | 0 | 448,355 | 0 | 122,086 | 326,268 | 1,279 | 100.0% |
| daily_net | 23,728 | 443,202 | 1,304 | 121,609 | 320,289 | 1,274 | 100.0% |
| daily_net_p95 | 634,288 | 271,703 | 34,845 | 66,150 | 170,708 | 693 | 95.6% |
| gross_batch | 1,288,262 | 140,727 | 70,772 | 31,405 | 38,550 | 329 | 49.9% |
| peak_p50 | 1,266,671 | 136,331 | 69,586 | 33,982 | 32,763 | 356 | 53.9% |
| peak_p75 | 1,409,623 | 114,192 | 77,439 | 17,373 | 19,380 | 182 | 27.6% |
| peak_p90 | 1,609,061 | 106,970 | 88,395 | 8,018 | 10,556 | 84 | 12.7% |
| peak_p95 | 1,764,892 | 109,352 | 96,956 | 4,868 | 7,527 | 51 | 7.7% |
| peak_p100 | 2,436,813 | 137,985 | 133,869 | 1,623 | 2,493 | 17 | 2.6% |
| oracle | 1,294,716 | 71,127 | 71,127 | 0 | 0 | 0 | 0.0% |

`peak_p90` is the cheapest policy at USD 106,970 a year. Holding nothing costs
USD 448,355. A buffer sized from the daily net position at its 95th percentile is
the textbook answer, holds USD 634,288 every night, and still misses a payout on
95.6 percent of days, because the account is short at 11:00 and settles at 16:30.
That is the finding: the daily net is the wrong quantity to take a percentile of,
and it is wrong by a factor of 2.5 on cost.

The mechanism is one number. Of the 720 days in the book, 393 have a positive net
flow. With no buffer, all 393 of them still run short before the 11:00 batch. A
positive daily net is not evidence that the account can pay.

The percentile sweep is shallow on the underfunded side and steep on the
overfunded side. From p50 to p90 the annual cost falls from USD 136,331 to
USD 106,970 as failed batches drop from 356 to 84. From p90 to the trailing
maximum it rises to USD 137,985 because carry grows faster than failures fall.
The optimum is a plateau between p80 and p95, not a point, so a treasury team
picking anywhere in that band lands within 4 percent of the best answer.

Fee sensitivity moves the plateau, which is why the policy should not be chosen
without the fee:

| Fee per failed batch | Best policy | Annual cost USD | peak_p90 USD | peak_p100 USD |
|---|---|---|---|---|
| USD 50 | peak_p75 | 100,294 | 100,555 | 136,686 |
| USD 250 | peak_p90 | 106,970 | 106,970 | 137,985 |
| USD 1,000 | peak_p95 | 123,956 | 131,024 | 142,853 |

Regimes, each rebuilt from the same seed with one parameter moved:

| Regime | Required float at p90 | peak_p90 annual USD | peak_p90 failures | zero buffer annual USD |
|---|---|---|---|---|
| baseline | 1,655,285 | 106,970 | 84 | 448,355 |
| settlement at the open | 305,080 | 33,638 | 73 | 56,927 |
| payout spikes 10 percent | 2,141,272 | 141,337 | 86 | 487,901 |
| volume steps up 25 percent at day 400 | 1,923,727 | 119,113 | 89 | 487,280 |
| batch one is 60 percent | 1,655,285 | 106,970 | 84 | 449,978 |
| slip 12 percent | 1,626,096 | 104,788 | 80 | 424,281 |

Two of those regimes are nulls and both are worth stating. Moving the settlement
from 16:30 to 08:00 cuts the required float by 82 percent, from USD 1,655,285 to
USD 305,080, and takes the best policy from USD 106,970 to USD 33,638 a year. The
schedule is worth more than the sizing, and it is the only lever here that
removes the problem instead of paying for it. Meanwhile moving the split between
the two payout batches from 45/55 to 60/40 changes nothing at all, to the cent,
because both batches clear before the late settlement arrives: the requirement is
the day's payouts minus the early inflow, and the split only decides when inside
the day the deficit appears.

A higher slip rate is also close to a null, and the reason is exact. The late
settlement slice lands at 16:30, after both payouts have left, so it funds
nothing today. Delaying it to the next morning raises tomorrow's early inflow and
lowers tomorrow's requirement, which is why a 12 percent slip rate ends up
slightly cheaper than 4 percent. Settlement reliability matters on the slice that
lands before 11:00, and only there.

The trailing window is not the lever either. At the 90th percentile, windows of
20, 40, 80 and 160 days cost USD 107,714, 106,970, 106,879 and 106,540. A volume
step of 25 percent, which should punish a long window, costs 11 percent more and
adds 5 failed batches, because the volume distribution is wide enough that the
step sits inside it.

The oracle, which knows each day's requirement in advance, costs USD 71,127. That
is the floor, and it is 34 percent below the best real policy. Most of the
remaining gap is information, not method.

## Limits

- Synthetic book. The volume, split, spike, and slip parameters are plausible for
  a mid size acquirer and are not calibrated to any real balance sheet. The
  ordering of the policies is the claim, not the dollar amounts.
- The failure model is a fee plus a facility charge. Real failed payouts lose
  merchants and attract regulatory attention, so the true cost of a failure is
  higher than USD 250, which would push the optimum to the right of p90.
- Net flow is break even by construction. A book with a growing balance would
  need less float, and a book in run off would need more.
- One currency, one account, no intraday credit line priced by utilisation, no
  bank holiday calendar, no weekend settlement.
- The buffer is a single number per day. A treasury that can move the payout
  cutoff, split the payout run, or hold a committed facility would beat every
  policy here, and this artifact does not model those moves.
- Nearest rank quantiles on a 40 day window cannot express anything above the
  97.5th percentile, so `peak_p100` is the trailing maximum by definition and is
  named that way rather than p99.
- The emergency facility charge is charged per day on the uncovered amount, not
  per hour. A genuinely intraday facility would price a 20 minute gap below a
  4 hour gap.

## Next

- Price the settlement schedule as an options problem: what is a 90 minute
  earlier settlement worth to this book, and what would treasury pay for it. The
  regime row says the answer starts around USD 73,000 a year.
- Replace the synthetic generator with the daily payout and settlement files a
  real processor can export, keeping the same `required_opening` ground truth.
- Add a second decision to the policy: move batch two to 16:45 and pay the
  merchant SLA for a later cutoff, which is a scheduling problem with a real
  price on both sides.
- Model a committed facility with a utilisation limit, so the policy chooses
  between holding cash and paying for a line it does not draw.
