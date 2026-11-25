# A cash machine is a stock with a flow problem

An ATM holds a lot of cash and sells withdrawals one at a time. Two costs pull in
opposite directions, the funding cost of the notes sitting in the cassette and the
fee for the armoured van that brings more. Most networks manage this with a cadence
and a fill-to-the-top rule. This artifact prices that habit against a min/max rule on
a synthetic 60 machine network, and separates the three costs that are usually
reported as one. Every number below is produced by the committed code.

## Problem

A cash plan answers two questions on every site: when does the van come, and how much
does it load. Operationally both questions get the same answer every week, because a
schedule is easy to run and easy to audit. The interesting failure is that the two
questions have different answers, and the second one carries most of the money.

Loading to capacity is the safe habit. It also parks cash: at INR 500 a note and a
750 basis point funding rate, every 1,000 notes left in a machine overnight costs
about INR 103 a year in funding, and a metro machine can hold 10,000. Running twice as
often halves the average balance and doubles the trip bill. Neither change is free,
and the machine's capacity decides whether a cheap cadence is even possible.

So the operator is choosing a point on a curve, but the tools usually report a
cadence, not the curve.

## Why it matters

On the book in `results/`, 60 machines dispensed 6,144,545 notes over 120 days, which
is INR 3,072,272,500 of cash across 898,883 withdrawals.

The default pattern, one trip a week on each site's fixed weekday with a fill to
capacity, costs INR 7,684,571.80 over the book and serves 99.423% of withdrawals. A
min/max rule that may send a van on any day, triggers when cover falls under three
days and fills to six, costs INR 6,597,770.30 and serves every withdrawal.

That is 16.47% cheaper and 0.577 percentage points better at the same time. The default
is not a tradeoff, it is dominated, and the reason is that it spends INR 1,069,957.70
more on cash it does not need to hold to save INR 91,999.20 on trips.

Priced against the value moved, the best practical policy costs 21.48 basis points of
the cash it dispenses. A perfect forecast would cost 18.94. The gap between them is
what the forecast is worth.

## Design

Five modules, one direction of data flow, money in integer paise.

- `cashplan/book.py`: the network and the demand. 60 sites in four kinds (metro,
  payday, resort, low traffic), a weekday shape per kind, a 30 day payday cycle, and a
  five day 1.55x surge on days 60 to 64 that no trailing forecast has seen. The book is
  generated once, before any policy runs, so every policy replays the same demand.
- `cashplan/forecast.py`: a trailing mean of the last four same weekday demands,
  multiplied by 1.10, using only rows strictly before the day being planned. Before
  enough history exists, the site's stated base load stands in.
- `cashplan/policies.py`: six policies as pure functions of (site, day, inventory,
  forecast). No policy sees demand, the book, or another site's result.
- `cashplan/sim.py`: the replay. Delivery, dispensing, closing balance, three cost
  lines, and a per site per day assertion that opening plus delivered equals dispensed
  plus closing and that closing stays inside capacity.
- `cashplan/bench.py`: the six policy runs, two capacity sweeps, and the derived
  comparisons the README quotes.

| Decision | Why | Tradeoff |
|---|---|---|
| Fill quantity is a separate control from cadence | The two have different costs and the fill is where the cash sits. Coupling them is what makes a cadence look like a policy | Two parameters per policy means the ladder has to be read as a set, not a single knob |
| Forecast is a trailing same weekday mean with a 1.10 uplift | It is what an operator can compute from their own history, and it cannot see the future, which a test asserts | It under-reacts to a step change by construction, so the 11.8% oracle gap is a floor on what better forecasting is worth |
| Trip fee flat per visit, INR 1,700 plus INR 0.20 a note | Simple, auditable, and the dominant cost in the result | Real cash in transit charges per route, not per stop, so this understates the cost of daily trips and biases the answer toward the min/max policy |
| Emergency trip at INR 3,600, only when the site cannot survive the day | Off schedule delivery has a real premium, and a policy should have to pay it | It is modelled as available to any policy that asks, which is optimistic for a same day callout |
| A lost withdrawal is priced at the INR 21 interchange it forgoes | It is the only defensible number in the model without customer data | It is far too low, which is why service is reported separately and the cheap rung of the capacity sweep is a warning rather than a recommendation |
| Perfect foresight as a reference policy, not a proven optimum | The oracle is a rule with the true demand, not a solver over all schedules, so it is an upper bound on performance, not the maximum | The gap to it is a price for forecast quality, not a statement about the optimal policy |
| Capacity swept uniformly across all sites | Holds demand fixed and moves one variable, so the cassette effect is isolated | A real network would resize the busy sites only, which would beat every rung of the sweep |
| Partial day service is pro rata on notes | Keeps the book at one row per site per day | An empty machine mid afternoon fails a share of arrivals that a pro rata split only approximates |

## Run

```bash
cd artifacts/2026-11-25-cash-logistics
PYTHONPATH=. uv run python -m cashplan.cli bench    # writes results/
PYTHONPATH=. uv run python -m cashplan.cli show     # prints without writing
```

Tests, from the lab root:

```bash
uv run pytest artifacts/2026-11-25-cash-logistics
```

35 tests, deterministic, no network, no wall clock, no sleeps. The suite runs in about
three seconds and the gate runs it twice to catch nondeterminism.

## Results

Synthetic network, seed 20261125, 120 days, 60 machines, 898,883 withdrawals,
6,144,545 notes, INR 3,072,272,500 dispensed. A note is INR 500. A trip is INR 1,700
plus INR 0.20 a note, an emergency trip is INR 3,600, funding is 750 basis points, and
a lost withdrawal is INR 21.

| Policy | Trips | Emergency | Service | Held notes | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|---|
| fixed_week_capacity | 1,029 | 0 | 99.423% | 6,203.1 | INR 2,987,131.00 | INR 4,588,597.80 | INR 108,843.00 | INR 7,684,571.80 |
| fixed_week_cover | 1,029 | 0 | 95.938% | 4,868.6 | INR 2,927,107.60 | INR 3,601,433.52 | INR 766,857.00 | INR 7,295,398.12 |
| fixed_fortnight_cover | 540 | 0 | 74.611% | 3,495.2 | INR 1,824,943.80 | INR 2,585,480.13 | INR 4,792,599.00 | INR 9,203,022.93 |
| minmax_3_6 | 1,091 | 0 | 100.000% | 4,756.7 | INR 3,079,130.20 | INR 3,518,640.10 | INR 0.00 | INR 6,597,770.30 |
| calendar_two_runs | 1,115 | 25 | 99.979% | 5,163.8 | INR 3,190,829.60 | INR 3,819,772.91 | INR 3,990.00 | INR 7,014,592.51 |
| oracle_minmax | 1,253 | 0 | 100.000% | 3,343.9 | INR 3,345,535.80 | INR 2,473,582.91 | INR 0.00 | INR 5,819,118.71 |

Held notes is the average closing balance per machine over the book, not a peak.

### Same trips, less cash, worse service

`fixed_week_cover` makes exactly the same 1,029 trips as the default and fills to seven
forecast days instead of the top. It releases INR 987,164.28 of funding cost and adds
INR 658,014.00 of lost withdrawals, a net saving of INR 389,173.68. That looks like a
win until the service line: 95.938%, down 3.486 points, which is 36,517 withdrawals
that found an empty machine.

This is the trap in the two question framing. The fill quantity can be cut without
changing the schedule, and the cost model will call it a saving, because a lost
withdrawal is priced at INR 21 and the cash it frees is worth more than that. A network
that manages by cost alone will walk into this.

### Fewer trips is the most expensive rung

`fixed_fortnight_cover` cuts the trip bill by 40.73% against the best policy, to
INR 1,824,943.80, and is 39.49% more expensive in total, because 25.39% of withdrawals
go unserved. It is the cheapest policy in the book on the two lines a spreadsheet
tracks (trips and cash) and the most expensive on the line it does not.

The capacity sweep on the fixed weekly cadence shows the same mechanism from the other
side. At three cassettes a weekly fill cannot cover a week at a metro site:

| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|
| 2 | 5,000 | 1,029 | 74.935% | INR 2,657,068.60 | INR 1,475,519.38 | INR 4,731,342.00 | INR 8,863,929.98 |
| 3 | 7,500 | 1,029 | 94.691% | INR 2,915,226.80 | INR 3,043,852.80 | INR 1,002,057.00 | INR 6,961,136.60 |
| 4 | 10,000 | 1,029 | 99.423% | INR 2,989,131.00 | INR 4,832,090.95 | INR 108,843.00 | INR 7,930,064.95 |
| 5 | 12,500 | 1,029 | 99.943% | INR 3,010,663.80 | INR 6,655,010.85 | INR 10,815.00 | INR 9,676,489.65 |
| 6 | 15,000 | 1,029 | 99.998% | INR 3,026,355.20 | INR 8,481,595.17 | INR 462.00 | INR 11,508,412.37 |

Four cassettes is the knee: service jumps from 94.691% to 99.423%, and every further
cassette above it buys fractions of a point for lakhs of rupees of idle cash. Meeting a
99.5% service target on a weekly cadence needs five cassettes and INR 9,676,489.65,
which is 46.66% more than the daily policy spends while serving every withdrawal. The
cheapest rung on this table is three cassettes at 94.691% service, because the model
prices a lost withdrawal at INR 21. Read that as the model telling you what it is
missing, not as a recommendation.

The same sweep on the daily min/max policy is the control that does not bind:

| Cassettes | Capacity | Trips | Service | CIT | Capital | Lost | Total |
|---|---|---|---|---|---|---|---|
| 2 | 5,000 | 3,195 | 100.000% | INR 6,666,632.80 | INR 2,193,951.57 | INR 0.00 | INR 8,860,584.37 |
| 3 | 7,500 | 1,465 | 100.000% | INR 3,721,721.00 | INR 2,949,146.40 | INR 0.00 | INR 6,670,867.40 |
| 4 | 10,000 | 1,079 | 100.000% | INR 3,056,951.80 | INR 3,553,913.93 | INR 0.00 | INR 6,610,865.73 |
| 5 | 12,500 | 973 | 100.000% | INR 2,871,950.00 | INR 3,882,770.03 | INR 0.00 | INR 6,754,720.03 |
| 6 | 15,000 | 939 | 100.000% | INR 2,797,718.40 | INR 3,918,001.84 | INR 0.00 | INR 6,715,720.24 |

With a trip allowed on any day, capacity never binds and every rung serves 100%: at two
cassettes the policy simply makes 3,195 trips. The curve from four to six cassettes is
flat within 1.5%, so the cassette count is a cost choice, not a service one, once the
schedule is flexible. Capacity only becomes a service constraint when the cadence is
fixed.

### What the schedule structure costs

`calendar_two_runs` restricts trips to Monday and Thursday and pays INR 3,600 when it
has to break the schedule, which it does 25 times. It reaches 99.979% service and costs
INR 7,014,592.51, 6.32% more than the unconstrained min/max for 190 unserved
withdrawals. That is the price of a two run week on this network.

### What the forecast is worth

The oracle policy knows tomorrow's demand. It costs INR 5,819,118.71, which is 11.8%,
or INR 778,651.59, below the best policy available with a trailing forecast. It does
not get there by tripping less: it makes 162 more trips and spends INR 266,405.60 more
on them, and it holds 1,412.8 fewer notes on average, which is worth INR 1,045,057.19
of funding. Better forecasting is a cash release programme that pays for extra trips.

### Where the default fails

The weekly full fill loses 5,183 withdrawals over the book. 5,123 of them, 98.84%, are
at metro sites, and 42 of its 44 stockout site days are metro days. The payday sites
lose 60 withdrawals and the resort and low traffic sites lose none. A single cadence is
not uniformly mediocre: it fails at the sites with the highest daily burn, which is
also where the vans already go most often.

## Limits

The demand book is synthetic. The weekday shapes, the payday multipliers and the 1.55x
surge are chosen to be the right shape and magnitude, not fitted to a real network, and
the seed is fixed. The levels are a property of this book, so a reader who wants their
own number has to replace the profiles in `cashplan/book.py`.

A lost withdrawal costs INR 21 here, which is the interchange a served withdrawal
earns and nothing else. No churn, no support cost, no lost deposit relationship. This
is the single largest understatement in the model, and it is why the capacity sweep's
cheapest rung is a 94.691% service level. The right way to use the cost column is next
to the service column, never instead of it.

A trip is priced per visit, not per route. Real cash in transit prices a run with
several stops, so a daily top up policy is cheaper here than it would be in the field,
and the two run calendar is closer to how a real route is bought than the model makes
it look. That biases the comparison toward the min/max policy.

Delivery has no lead time: the van arrives at the start of the day it is called. A real
callout takes a day or more, so the emergency premium is a lower bound and the policy
that relies on it is flattered.

Capacity is swept uniformly across all 60 sites. A real answer resizes the 24 metro
machines and leaves the rest, which would beat every rung of the sweep and is the
obvious next experiment.

Service is computed pro rata on notes within a day, so a machine that empties at noon
is treated as serving a proportional share of that day's arrivals rather than the
earlier ones.

The oracle is a min/max rule with perfect demand, not a solver over all possible
schedules, so the 11.8% is a price for forecast quality, not the true value of perfect
information. A solver would find a lower floor.

One denomination. A real cassette mix has to be balanced across notes, and a machine
can hold cash it cannot dispense because it ran out of the small note. That failure is
not in this model.

## Next

1. Sweep capacity per site kind instead of uniformly, which is the change a real
   network would actually buy, and price the 24 metro machines against the other 36.
2. Add a route: one fee per run, several stops per run, and a stop limit. That is the
   control that decides whether daily top ups are affordable, and it is the one the
   flat per visit fee currently flatters.
3. Price a lost withdrawal properly: churn, support, and the deposit relationship. The
   fortnightly policy should get much worse, and the capacity sweep's cheap rung should
   disappear.
4. Add a cassette mix and the note level stockout, which is the failure mode cash
   managers actually argue about.
5. Replace the trailing forecast with a weekday plus payday model on the same book, and
   measure how much of the 11.8% oracle gap it closes.
