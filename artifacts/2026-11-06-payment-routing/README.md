# Routing on approval rate, not on price

Every card payment is routed to one acquirer. The fee schedule is in the contract. The
approval rate is not, and it differs by segment, so the cheapest provider on paper is often
the most expensive one in practice.

Headline: on 50,000 synthetic transactions at a 15 percent gross margin, routing on the
lowest published fee collects 26.9 basis points less in fees and still gives up 4.0 percent
of net margin, $1,531 per 1,000 transactions. Authorization is 88.9 percent against 94.3
percent for a router that knows the approval curve.

## Problem

A payment router picks one provider for one attempt, and gets a yes or a no. The fee is
published and computable per ticket. The probability of the yes is not published, changes by
card type, region and ticket size, and changes again when an issuer relationship moves.

So there are two ways to be wrong:

- Route to the cheapest provider and lose the sale to a decline. The fee saved is 30 basis
  points; the sale lost is the whole margin, which is 15 percent of the ticket.
- Route to the provider with the best historical approval rate and pay for it on every
  transaction, including the segments where it is not better.

The decision is a priced bet, not a search result, and the price of being wrong is
asymmetric.

## Why it matters

Fees are roughly 1.2 to 1.9 percent of a ticket. Gross margin is often 10 to 25 percent. That
means one percentage point of authorization is worth 0.10 to 0.25 percent of volume, and a
fee difference of 30 basis points is worth 0.30 percent. The two are the same order of
magnitude, which is why teams argue about routing for years and why the answer depends on
the merchant's margin, not on the provider's pitch.

This bench measures the argument instead of restating it. It also shows the part that
vendor decks leave out: on this book the fee-only choice is the wrong choice in 9 of 12
segments and the worst of the three providers in 7 of them.

## Design

A synthetic book of transactions, three providers with published fees and hidden approval
curves, six routing policies, one ledger.

### The book

- 50,000 transactions, seeded, labelled synthetic. No real card, cardholder or issuer.
- 12 segments: credit or debit, domestic or cross border, and a ticket band of micro (3 to
  30 dollars), mid (30 to 200) or large (200 to 1,500). Mean ticket is 313 dollars.
- Band mix is 25 percent micro, 45 percent mid, 30 percent large. 55 percent debit, 22
  percent cross border.
- `routelab.data.digest` hashes the book and the hash is committed in `results/summary.json`
  (today `eb0f27f3d9be0528`), so a number can be traced to the exact book that produced it.

### The providers

| Provider | Fee | Strength (hidden from the router) |
|---|---|---|
| alpha | 1.20% + 8c | domestic credit, large tickets; weak debit and cross border |
| bravo | 1.55% + 4c | debit; cheaper than alpha below about 11 dollars |
| charlie | 1.85% + 0c | cross border and large tickets; weakest on micro |

Fees cross over at small tickets: at 10 dollars charlie is cheapest by a cent, at 8 dollars
bravo is, and above 12 dollars alpha always is. That is deliberate. A fee schedule with a
fixed component is not a single ranking, so "the cheapest provider" is already a per-ticket
question before approval enters it.

Approval is a logistic model per provider with segment coefficients: alpha is strong on
domestic credit and weak on debit and cross border, bravo is the debit specialist, charlie
owns cross border and large tickets and is worst on micro. The router never sees these
coefficients. It sees outcomes.

### Outcomes and retries

- Each attempt draws from the provider's approval probability for that transaction.
- Uniforms are derived from `blake2b(seed, transaction, provider, attempt)`, so every policy
  sees the same luck on the same attempt. Comparisons are paired: the difference is the
  routing decision, not the draw.
- 35 percent of declines are hard (stolen card, closed account) and cannot be recovered. A
  soft decline can be retried, at 55 percent of the next provider's own approval
  probability. The default depth is one retry, which is what a checkout does.

### The ledger

All money is integer cents, fees round half up once, and every run must satisfy
`net = gross margin - fees - ops`, where ops is 2 cents per attempt. The test suite
recomputes the whole run independently and compares totals, so a sign flip cannot pass as a
zero residual.

### The policies

| Policy | What it does |
|---|---|
| `cheapest` | Rank by published fee for this ticket. The contract view. |
| `static_rules` | Cross border to charlie, debit to bravo, everything else to alpha; the rest by fee. The vendor-deck view. Ticket size never enters. |
| `epsilon_greedy` | Mean realized net per segment and provider, 10 percent exploration. |
| `thompson` | Beta posterior on approval per segment and provider, all history, sampled and costed per attempt. |
| `thompson_window` | Same sampler, posterior from the last 300 attempts per segment and provider. |
| `oracle` | The true model, ranked by expected net. A reference line, not a deliverable. |

### Decisions and tradeoffs

| Decision | Alternative | Why this way | What it costs |
|---|---|---|---|
| Maximise net margin per attempt | Maximise authorization rate | Authorization alone recommends the most expensive provider every time; the merchant pays for captures, not for approvals | Needs the margin assumption, which is swept |
| Rank providers, retry down the list | Pick one provider | A declined checkout is retried in production anyway; ignoring that flatters bad routing | Ranking is harder to state than a single rule |
| Same random draws for every policy | Fresh randomness per policy | Paired comparison removes draw noise from the gap | Results are conditional on one outcome seed |
| Hidden per-segment approval | Published average approval | Provider averages are marketing; segment behaviour is what routing acts on | Every provider looks identical on a headline number |
| Known fees, learned approval | Learn both | Fees are in the contract, so learning them wastes traffic | Assumes the schedule is stable, which holds for a quarter |
| 35 percent hard declines | All declines retryable | Retrying a stolen card is pure cost, and real systems get reason codes | Simplifies issuer behaviour into one flag |
| Window of 300 attempts | Full history | Full history is stable but cannot see a provider change; a window can | Noisy estimates, visible as a lower steady-state number |
| Oracle ignores the retry option | Solve the optimal stopping problem | It is a reference line, and the simpler version is stricter | The rule table can land a hair above it |

## Run

```
cd /Users/parthbatra/fintech-lab
PYTHONPATH=artifacts/2026-11-06-payment-routing uv run python -m routelab.cli route
uv run pytest artifacts/2026-11-06-payment-routing
```

The first command rewrites `results/summary.json` and `results/summary.md` in about 6
seconds. The second is deterministic: no network, no wall clock, no sleeps. 34 tests, under
a second.

## Results

Produced by the commands above, committed in `results/`.

```
book 50000 synthetic transactions, digest eb0f27f3d9be0528
margin 15.0% of ticket, ops 2c per attempt, retry depth 1

policy           att/txn   auth%  fee bps  net $/1000  vs cheapest
cheapest            1.10   88.9%    124.4   38,271.18        +0.00
static_rules        1.05   94.3%    150.7   39,824.57    +1,553.39
epsilon_greedy      1.07   92.3%    151.6   39,441.33    +1,170.15
thompson            1.06   93.9%    150.2   39,778.31    +1,507.13
thompson_window     1.07   92.9%    138.7   39,190.48      +919.30
oracle              1.05   94.3%    151.3   39,801.84    +1,530.66
```

Where the fee-only choice is wrong, per segment (single attempt expectation, so these are
larger than the realized gap, which is already reduced by one retry):

```
segment                             n  ticket  fee arm    best   gap $/txn
debit/cross_border/large         1841     848    alpha charlie       25.00
credit/cross_border/large        1496     857    alpha charlie       10.19
debit/domestic/large             6462     849    alpha   bravo        6.80
debit/cross_border/mid           2719     117    alpha charlie        3.17
credit/cross_border/mid          2169     116    alpha charlie        1.13
debit/domestic/mid               9728     114    alpha   bravo        0.95
debit/cross_border/micro         1504      17    alpha charlie        0.49
credit/domestic/micro            4362      17  charlie   alpha        0.28
debit/domestic/micro             5346      17  charlie   bravo        0.26
credit/cross_border/micro        1253      17  charlie charlie        0.00
credit/domestic/large            5305     852    alpha   alpha        0.00
credit/domestic/mid              7815     115    alpha   alpha        0.00
```

The control, swept three ways:

```
retry depth sweep
 depth  cheap auth%  oracle auth%  cheap fee bps  gap $/1000
     0        83.7%         91.7%          122.5    2,688.78
     1        88.9%         94.3%          124.4    1,530.66
     2        90.5%         95.0%          125.6    1,150.78

margin assumption sweep
  margin%   cheapest $/1000  oracle $/1000    gap %
       10         24,352.42      25,062.60      2.9
       15         38,271.18      39,801.84      4.0
       22         57,757.61      60,471.32      4.7
```

A provider's approval rate moving mid-stream, with `bravo` losing 0.90 logit on debit at
transaction 25,000:

```
policy            net before  net after    change  auth after
cheapest           38,066.60  38,341.04   +274.44       88.5%
static_rules       39,789.14  38,618.72 -1,170.42       91.2%
thompson           39,756.97  38,481.39 -1,275.58       90.4%
thompson_window    39,030.95  38,987.56    -43.39       90.3%
oracle             39,841.54  38,969.57   -871.97       91.8%

net $ per 1000 by block after the shift
 block     static   thompson    window    oracle
     6  38,975.99  38,794.31 40,082.95 40,061.90
     7  39,454.01  39,302.32 39,597.76 39,418.84
     8  37,599.16  37,557.64 37,722.88 37,871.40
     9  39,494.34  39,326.37 39,585.31 39,557.27
    10  37,570.10  37,426.31 37,948.91 37,938.44
```

What the numbers say:

- **The fee is a bad proxy for the cost.** The cheapest router pays 124.4 basis points and
  keeps 38,271 dollars per 1,000 transactions. The reference pays 151.3 basis points and
  keeps 39,802. It buys 5.4 points of authorization with 26.9 basis points of fee, and that
  trade is worth four times what it costs.
- **The loss is concentrated, not diffuse.** 3,337 cross-border large transactions, 6.7
  percent of the book, are worth 25 and 10 dollars each in expectation when routed to alpha
  instead of charlie. The three segments where the fee choice is right are all domestic
  credit.
- **A human rule table gets almost all of it.** Three lines from the vendor decks recover
  1,553 dollars per 1,000, which is 4.06 percent and slightly more than the reference, because
  the reference ignores the retry option and the rules do not. The learned routers do not beat
  the rules in steady state: Thompson lands 0.1 percent below, epsilon greedy 1.0 percent
  below, and the window pays 1.8 percent for its adaptability.
- **Retries hide the defect.** At depth zero the gap is 2,689 dollars per 1,000. One retry cuts
  it to 1,531, two to 1,151. A merchant with a retry ladder can look acceptable on conversion
  while still routing badly, and pays for it in fees: the cheap router's fee load climbs from
  122.5 to 125.6 basis points as depth goes from 0 to 2, while the rule table stays at 151.
- **The margin assumption moves the answer, not the direction.** At a 10 percent margin the
  gap is 2.9 percent, at 22 percent it is 4.7 percent. Grocery and jewellery should not use the
  same routing table, which is the part a single vendor benchmark cannot say.
- **Full history cannot see a regime change.** After bravo degrades, the all-history posterior
  is too tight to notice and gives up 1.25 percent against the reference, slightly worse than
  the rules it was supposed to replace. The 300 attempt window gives up 0.05 percent, and pays
  for it before the shift with a 1.8 percent shortfall. Adaptability is a setting with a price,
  not a property of "AI routing".

## Limits

- **The book is synthetic and I wrote the generator, the coefficients and the fees.** The
  segment gaps are designed to be plausible, not measured from a real portfolio. Precision
  here is a property of my assumptions. Treat the shape of the result as the claim, not the
  dollar figure.
- **The rule table was written after the model.** I knew which provider was strong where when
  I wrote the three lines, which no real team does. That makes 1,553 dollars an upper bound on
  hand-written rules, and the four percent gap between fee-only and rules a lower bound on what
  a thoughtful table can recover.
- **The reference ignores the retry option and ignores exploration.** It ranks by single
  attempt expected net, so it is a floor on the true optimum and can be beaten by a policy that
  happens to catch a better draw sequence. `static_rules` sits 0.06 percent above it for that
  reason.
- **Approval outcomes are independent across providers for a given transaction.** Real
  declines correlate (a closed account declines everywhere), which would make retries less
  valuable than measured here and narrow the routing gap.
- **Hard and soft decline types are drawn per attempt, not per card.** Real systems see a
  reason code and a card history; both are collapsed into one flag at 35 percent.
- **No interchange, scheme fees, 3DS, latency, outages or partial approvals.** The fee is the
  provider markup only. Latency matters for routing decisions in production and is absent.
- **Chargebacks and refunds are absent.** A provider that approves more transactions because
  it is lax on fraud looks strictly better in this bench. Adding dispute cost would change the
  ranking, and that is the first thing I would fix.
- **The context is 12 buckets.** A production router sees issuer BIN, MCC, device, currency
  and velocity, and would need far more traffic per bucket than 50,000 transactions.
- **Exploration is measured on live simulated traffic.** The learning curve is honest for this
  simulator; a real deployment needs a holdout and off-policy evaluation, because the traffic a
  bad policy generates is the traffic it learns from.
- **The window of 300 attempts and the 10 percent exploration rate were chosen by hand**, not
  tuned, and both are reported as single points.

## Next

1. Add dispute and refund cost to the reward, so approving more fraud is not free, and re-run
   the table. This is the assumption most likely to reorder the providers.
2. Evaluate offline with a fixed logged policy plus importance weights, and compare against
   the on-policy numbers here, to show how much a bandit flatters itself.
3. Replace the fixed window with change point detection, and charge it for the detection
   delay it actually incurs.
4. Add latency as a constraint rather than a metric: a provider that approves 2 points more
   but times out at the 95th percentile is not a better route.
