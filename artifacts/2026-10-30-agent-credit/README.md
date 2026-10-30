# Credit between agents that never know who owes whom

A clearing house for agent to agent payments: per member credit limits, multilateral
netting at the window close, and a default that costs exactly what the limit allows.

The claim: a cap on gross outflow is a poor proxy for settlement risk in an agent market.
Over 3,000 synthetic obligations, a $200 cap on gross outflow carried 21.26% of the value.
A $200 cap on net debit carried 97.84%. Both ended with a worst case loss under $200.
Multilateral netting removed 94.59% of the money that would have moved.

## Problem

Twelve agents trade with each other all day. At the close of the window, every obligation
is supposed to settle. Two things break.

1. Somebody has to carry the float. Agent A pays agent B at 09:00 and is paid by agent C
   at 17:00. Between those two events A is lending the market money, and nobody granted it
   credit. If A disappears at 16:59, C is fine and B is not.
2. Most of the money does not need to move at all. In one window of this simulation,
   $11,385.94 of obligations were cleared by $568.84 of actual payments, because the agents
   are largely paying each other in circles.

So the risk question is not "how much is this agent sending". It is "how much will this
agent still owe when the music stops". Those two numbers differ by a factor of 4.8 in the
data below, and a limit built on the first one throttles the market while measuring the
wrong thing.

## Why it matters

The thing being underwritten here is not a payment. It is the gap between when an agent
pays and when it is paid, and that gap is now machine speed and machine scale.

- **A gross flow limit is the obvious implementation and it is the wrong control.** Every
  payments engineer writes `if spent + amount > limit: reject`. It is correct for a spend
  card and wrong for a clearing member, because a router with $10,000 in and $10,000 out
  has zero settlement risk and gets refused at $600 of outflow.
- **Netting converts a payment problem into a credit problem.** Removing 94.59% of the
  flow sounds like a pure win. It is also a transfer of risk: the members now depend on
  the whole set settling, and the defaulter's gross obligations (4.81x its net debit) are
  the size of that dependency.
- **An agent market has no relationship managers.** When the counterparty is a process,
  the limit has to be computable from the ledger at decision time, in one pass, with no
  human in the loop. That is what this artifact measures.

## Design

Four modules, integer minor units throughout, no clock and no network.

- `creditnet/ledger.py`: `Obligation(payer, payee, amount, ts)` and `Ledger`. Positions,
  bilateral balances, and `imbalance()`, which sums every position and must be zero.
  A self payment and a non positive amount are refused at construction.
- `creditnet/credit.py`: `CreditBook`. Three rules over the same flow: `unlimited`,
  `gross_cap` (committed outflow plus the new amount must fit the limit), `net_cap`
  (committed outflow plus the new amount minus committed inflow must fit). Inflow only
  counts obligations already admitted, which is all a clearing house knows at decision
  time.
- `creditnet/netting.py`: `settlement()` pairs debtors with creditors in name order and
  emits one instruction per pair, plus `bilateral_settlement_value()` for the middle rail
  where each pair nets separately. Both are computed independently so the three volumes
  can be compared rather than assumed.
- `creditnet/sim.py`: the market and the three experiments. Flows are 18 random cycles of
  3 to 5 agents plus one way noise up to 150 obligations per window, seeded, synthetic.
  Cycles are what netting eats, so shaping the flow this way is the honest way to test it,
  and it is stated as a parameter rather than hidden in a random draw.

### Decisions and tradeoffs

| Decision | Alternative | Why this one |
|---|---|---|
| Net debit limit as the control | Gross outflow cap | Caps the number that actually gets lost at default, and leaves a router alone. The measured cost of the alternative is the 21.26% against 97.84% table |
| Multilateral netting per window | Bilateral netting | Bilateral removed 68.76% against 94.59%. A cycle of five agents nets to zero only if all five are in the same set |
| Inflow counts only after admission | Count promised future inflows | A promise from a member that later fails is the thing being insured. Using it as collateral is how clearing houses blow up |
| Integer minor units | `Decimal` or float | The invariant under test is an exact zero, and floats cannot prove one |
| Seeded synthetic cycles | Random uniform pairs | Uniform pairs net to almost nothing, which would flatter the gross rule and make the comparison meaningless. The cycle share is the load bearing parameter and it is stated |
| Default loss = the defaulter's net debit | A waterfall with margin and a clearing fund | The waterfall is the next artifact, not this one. Stating the shortfall exactly is enough to bound it |
| Uniform static limits across the sweep | Per agent risk based limits | One dial at a time. A per agent limit changes both the admission rate and the loss cap, and then neither number can be attributed |
| Every rule scored on the same windows | Regenerate the market per rule | Same 3,000 obligations and same victim in all three runs, so the difference is the rule, not the draw |

## Run

From the repository root:

```
PYTHONPATH=artifacts/2026-10-30-agent-credit uv run python -m creditnet.cli bench
```

That prints the tables below and rewrites `results/` (five JSON files and `summary.md`).
Under a second, no network, no keys.

One window in detail, optionally at another limit:

```
PYTHONPATH=artifacts/2026-10-30-agent-credit uv run python -m creditnet.cli window 0 --limit 20000
```

Tests:

```
uv run pytest artifacts/2026-10-30-agent-credit
```

44 tests, deterministic, no clock and no network. One test regenerates `results/` into a
temporary directory and checks it byte for byte against a second run, and another compares
the committed `results/summary.json` against a fresh computation, so the numbers here
cannot drift from the code that produced them.

## Results

Synthetic market: 12 agents, 20 settlement windows, 150 obligations per window, 3,000 in
total, seed 20261030, uniform limit of $600 per member per window unless stated.

### Does netting remove flow, and do the books still balance

| Rail | Value that moves | Removed vs gross |
|---|---|---|
| Gross, every obligation pays | $215,945.19 | 0.0% |
| Bilateral netting, per pair | $67,465.48 | 68.76% |
| Multilateral netting, per window | $11,687.43 | 94.59% |

Every position in every window sums to zero: 20 of 20 windows, all three rules. The
invariant is asserted as an equality between independently computed values, not as
`residual == 0`.

### Which limit admits the market

Same 3,000 obligations, same victim, five limit levels. Worst loss is the largest single
window shortfall when the largest net debtor fails at the close.

| Limit | Gross cap admits | Gross cap worst loss | Net cap admits | Net cap worst loss |
|---|---|---|---|---|
| $200 | 21.26% | $196.67 | 97.84% | $197.14 |
| $400 | 43.18% | $321.15 | 99.99% | $395.33 |
| $600 | 63.98% | $390.31 | 100.0% | $420.33 |
| $900 | 87.51% | $458.39 | 100.0% | $420.33 |
| $1,500 | 99.78% | $420.33 | 100.0% | $420.33 |

Read the $200 row: at the same one window loss ceiling of about $200, the net debit rule
carried 4.6x the payment value. The gross rule's admission rate climbs slowly and only
reaches the market at a limit 7.5x larger than the loss it ever needs to cover.

The gross rule's worst loss is lower than the net rule's at $200 and $400. That is not
better risk management, it is a smaller market: it refuses 78.74% of the value at $200,
so the positions it leaves behind are small. At $900 the ordering flips, which is the
signature of a control that tracks something other than the risk.

At the $600 reference limit, the net cap admits all 3,000 obligations ($215,945.19) and
still never lets a member's net debit exceed $600. The gross cap refuses 1,303 of them
($77,773.82) and the flow it refuses is the flow that nets.

### What a default costs

The declared victim is the largest net debtor in each window, chosen from the unlimited
run so it is the same agent under all three rules.

| Measure | Value |
|---|---|
| Mean net debit of the defaulting agent | $217.20 |
| Mean gross outflow of that agent | $935.80 |
| Ratio, gross sent to net owed | 4.81x |
| Fund needed to cover the worst window, net cap | $420.33 |
| Windows where a member's net debit passed $200 with no rule | 10 of 20 |

The 4.81x is the whole argument for netting and the whole risk of it, in one number. The
agent's counterparties only ever needed $217.20 from it, and they were exposed to $935.80
of payments until the netting set held.

## Limits

- **The flows are synthetic.** Cycle depth is the parameter that drives the 94.59%, and
  this market is 18 cycles per 150 obligations. A market of one way payments would net far
  less. No real venue, counterparty, or credit file was used, and no number here is a
  claim about any of them.
- **The netting benefit is contingent on the set holding.** If the defaulting agent stops
  paying, its net debit is the shortfall and everyone else's net credit is short by that
  amount. Close out netting against a defaulted counterparty is a legal question that
  code cannot answer. This artifact measures the exposure, not the enforceability.
- **No waterfall.** There is no pre-funded margin, no clearing fund, no loss mutualization
  and no second default. A single failure is charged at its net debit and the run stops.
- **Limits do not replenish.** A refused obligation never retries, and headroom is not
  released when an offsetting inflow arrives later in the window. A real member would
  resubmit, which would raise both admission rates.
- **One currency, no prices, no rates.** Amounts are integer minor units of a single
  currency. FX conversion between legs would change both the netting arithmetic and the
  default loss.
- **No timing model.** All obligations in a window are treated as simultaneous. Settlement
  order and cut off times decide which obligations a failing member actually gets to skip.
- **Uniform limits.** Every member gets the same credit, which no real clearing house
  would do. It makes the sweep a one dial experiment and it is why the numbers should not
  be read as a recommendation for a limit policy.

## Next

1. Add a default waterfall: pre-funded margin per member, then a mutualized clearing fund,
   and test that member losses stay at zero until the fund is exhausted, with the fund size
   as a measured output rather than an assumption.
2. Make the limit a function of observed behaviour: a member whose net position stays near
   zero gets a gross limit, a member that runs a real debit gets a net limit. Measure the
   admission gain over the uniform rule at the same worst case loss.
3. Add a second default in the same window and measure how the shortfall compounds once the
   surviving members can no longer be assumed to settle.
4. Give obligations a deadline. A failing member that misses an early obligation is a
   different risk from one that misses the last one, and the limit should decay with the
   window.
